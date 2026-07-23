"""Tests for the company header agent."""

from __future__ import annotations

import json
import sys
import threading
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from company_header_agent.a2a_server import (
    _build_handler,
    build_agent_card,
    handle_jsonrpc_request,
)
from company_header_agent.openai_agent import (
    create_openai_agent,
    run_company_header_agent,
)
from company_header_agent.tools import get_company_name, inject_company_header


def test_inject_company_header_inserts_header_before_main() -> None:
    """Verify the header is inserted as a body child before main content."""
    html_document = "<!doctype html><html><body><main><p>Hello</p></main></body></html>"

    result = inject_company_header(html_document, "Example Australian Company")

    assert result == (
        "<!doctype html><html><body>\n"
        "<header>Example Australian Company</header>\n"
        "<main><p>Hello</p></main></body></html>"
    )


def test_inject_company_header_escapes_company_name() -> None:
    """Verify company names are escaped before insertion into markup."""
    html_document = "<html><body><main></main></body></html>"

    result = inject_company_header(html_document, "A&B <Company>")

    assert "<header>A&amp;B &lt;Company&gt;</header>" in result


def test_inject_company_header_requires_body_element() -> None:
    """Verify malformed documents without body fail explicitly."""
    with pytest.raises(ValueError, match="<body>"):
        inject_company_header("<main></main>", "Example Australian Company")


def test_get_company_name_reads_mcp_sidecar_resource(monkeypatch) -> None:
    """Verify company name reads the configured MCP sidecar resource."""
    calls = []

    def fake_call(sidecar_url: str, resource_uri: str) -> str:
        calls.append((sidecar_url, resource_uri))
        return "Example Australian Company"

    monkeypatch.setenv("MCP_SIDECAR_URL", "http://mcp-sidecar:8000/mcp")
    monkeypatch.setattr("company_header_agent.tools._call_mcp_resource", fake_call)

    assert get_company_name() == "Example Australian Company"
    assert calls == [
        (
            "http://mcp-sidecar:8000/mcp",
            "mcp-sidecar://company/name.txt",
        )
    ]


def test_create_openai_agent_uses_company_header_tools(monkeypatch) -> None:
    """Verify the agent is configured with the required tools."""
    calls = []

    class _FakeAgent:
        def __init__(self, **kwargs: Any) -> None:
            calls.append(kwargs)

    _install_fake_agent_dependencies(monkeypatch, agent=_FakeAgent)

    create_openai_agent()

    assert calls[0]["name"] == "Company Header HTML Updater"
    assert calls[0]["model"] == "gpt-4.1-mini"
    assert calls[0]["tools"] == [
        "tool:get_company_name",
        "tool:inject_company_header",
    ]
    assert "return only the updated HTML document" in calls[0]["instructions"]


def test_run_company_header_agent_returns_updated_html(monkeypatch) -> None:
    """Verify Runner receives the input HTML and returns the model output."""
    calls = []

    class _FakeAgent:
        def __init__(self, **kwargs: Any) -> None:
            calls.append({"type": "agent", **kwargs})

    class _FakeRunner:
        @staticmethod
        def run_sync(
            agent: _FakeAgent,
            prompt: str,
            max_turns: int,
        ) -> SimpleNamespace:
            calls.append(
                {
                    "type": "run",
                    "agent": agent,
                    "prompt": prompt,
                    "max_turns": max_turns,
                }
            )
            return SimpleNamespace(final_output="<html><body>updated</body></html>")

    _install_fake_agent_dependencies(
        monkeypatch,
        agent=_FakeAgent,
        runner=_FakeRunner,
    )

    result = run_company_header_agent("<html><body><main></main></body></html>")

    assert result == "<html><body>updated</body></html>"
    assert calls[0]["type"] == "agent"
    assert calls[1]["type"] == "run"
    assert "Use the get_company_name tool first" in calls[1]["prompt"]
    assert "<html><body><main></main></body></html>" in calls[1]["prompt"]
    assert calls[1]["max_turns"] == 6


def test_build_agent_card_describes_a2a_endpoint() -> None:
    """Verify the Agent Card advertises the A2A endpoint and skill."""
    card = build_agent_card("http://company-header-agent:8080")

    assert card["name"] == "Company Header Agent"
    assert card["url"] == "http://company-header-agent:8080/a2a"
    assert card["defaultInputModes"] == ["text/html", "text/plain"]
    assert card["defaultOutputModes"] == ["text/html"]
    skills = card["skills"]
    assert isinstance(skills, list)
    assert skills[0]["id"] == "inject_company_header"


def test_handle_jsonrpc_message_send_returns_updated_html() -> None:
    """Verify message/send returns an A2A message containing updated HTML."""
    request = {
        "jsonrpc": "2.0",
        "id": "request-1",
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [
                    {
                        "kind": "text",
                        "text": "<html><body><main></main></body></html>",
                    }
                ],
            }
        },
    }

    response = handle_jsonrpc_request(
        request,
        lambda html_document: html_document.replace(
            "<main>", "<header></header><main>"
        ),
    )

    assert response["jsonrpc"] == "2.0"
    assert response["id"] == "request-1"
    result = response["result"]
    assert isinstance(result, dict)
    assert result["kind"] == "message"
    parts = result["parts"]
    assert isinstance(parts, list)
    assert parts[0]["text"] == (
        "<html><body><header></header><main></main></body></html>"
    )


def test_handle_jsonrpc_rejects_unknown_method() -> None:
    """Verify unsupported A2A methods fail as JSON-RPC errors."""
    response = handle_jsonrpc_request(
        {
            "jsonrpc": "2.0",
            "id": "request-1",
            "method": "tasks/get",
            "params": {},
        },
        lambda html_document: html_document,
    )

    assert response["error"] == {
        "code": -32601,
        "message": "Unsupported method: tasks/get",
    }


def test_a2a_http_server_exposes_agent_card_and_message_endpoint(
    monkeypatch,
) -> None:
    """Verify the HTTP server exposes discovery and A2A exchange endpoints."""
    monkeypatch.setattr(
        "company_header_agent.a2a_server.run_company_header_agent",
        lambda html_document, model: f"{html_document}\n<!-- {model} -->",
    )
    handler = _build_handler("gpt-4.1-mini", "http://127.0.0.1:0")
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base_url = f"http://127.0.0.1:{server.server_port}"
        card = _read_json(f"{base_url}/.well-known/agent.json")

        assert card["url"] == "http://127.0.0.1:0/a2a"
        response = _post_json(
            f"{base_url}/a2a",
            {
                "jsonrpc": "2.0",
                "id": "request-1",
                "method": "message/send",
                "params": {
                    "html_document": "<html><body><main></main></body></html>",
                },
            },
        )
        result = response["result"]
        assert isinstance(result, dict)
        parts = result["parts"]
        assert isinstance(parts, list)
        assert parts[0]["text"].endswith("<!-- gpt-4.1-mini -->")

        with pytest.raises(HTTPError) as error:
            _read_json(f"{base_url}/missing")

        assert error.value.code == 404
    finally:
        server.shutdown()
        thread.join(timeout=5)


def _install_fake_agent_dependencies(
    monkeypatch,
    *,
    agent: type | None = None,
    runner: type | None = None,
) -> None:
    if agent is None:

        class _FakeAgent:
            def __init__(self, **kwargs: Any) -> None:
                pass

        agent = _FakeAgent

    if runner is None:

        class _FakeRunner:
            @staticmethod
            def run_sync(
                agent: Any,
                prompt: str,
                max_turns: int,
            ) -> SimpleNamespace:
                _ = agent
                _ = prompt
                _ = max_turns
                return SimpleNamespace(final_output="ok")

        runner = _FakeRunner

    fake_agents_module = SimpleNamespace(
        Agent=agent,
        Runner=runner,
        function_tool=lambda function: f"tool:{function.__name__}",
    )
    fake_openai_tools_module = SimpleNamespace(
        get_company_name_tool="tool:get_company_name",
        inject_company_header_tool="tool:inject_company_header",
    )
    monkeypatch.setitem(sys.modules, "agents", fake_agents_module)
    monkeypatch.setitem(
        sys.modules,
        "company_header_agent.openai_tools",
        fake_openai_tools_module,
    )


def _read_json(url: str) -> dict[str, object]:
    request = Request(url, method="GET")
    with urlopen(request, timeout=5) as response:
        data = response.read().decode("utf-8")

    result = json.loads(data)
    assert isinstance(result, dict)
    return result


def _post_json(url: str, body: dict[str, object]) -> dict[str, object]:
    request = Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=5) as response:
        data = response.read().decode("utf-8")

    result = json.loads(data)
    assert isinstance(result, dict)
    return result
