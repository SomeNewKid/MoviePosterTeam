"""Tests for the Writer Agent package."""

from __future__ import annotations

import json
import sys
from types import SimpleNamespace
from typing import Any

from writer_agent.a2a_server import _handle_json_rpc_request
from writer_agent.openai_agent import create_writer_agent, run_writer_agent


def test_create_writer_agent_uses_movie_concept_identity(monkeypatch) -> None:
    """Verify the Writer Agent is configured as a movie concept generator."""
    calls = []

    class _FakeAgent:
        def __init__(self, **kwargs: Any) -> None:
            calls.append(kwargs)

    _install_fake_agent_dependencies(monkeypatch, agent=_FakeAgent)

    create_writer_agent()

    assert calls[0]["name"] == "Movie Concept Writer"
    assert calls[0]["model"] == "gpt-4.1-mini"
    assert "valid JSON" in calls[0]["instructions"]


def test_run_writer_agent_returns_structured_movie_json(monkeypatch) -> None:
    """Verify Writer Agent output is parsed into the required schema."""
    prompts = []

    class _FakeRunner:
        @staticmethod
        def run_sync(agent: object, prompt: str, max_turns: int) -> SimpleNamespace:
            _ = agent
            prompts.append((prompt, max_turns))
            return SimpleNamespace(
                final_output=json.dumps(
                    {
                        "title": "The Last Marquee",
                        "tagline": "Every light hides a memory.",
                        "synopsis": (
                            "A projectionist discovers a city inside old film reels."
                        ),
                        "genre": "fantasy mystery",
                        "visual_style": "noir cinema glow with surreal architecture",
                    }
                )
            )

    _install_fake_agent_dependencies(monkeypatch, runner=_FakeRunner)

    result = run_writer_agent("Make it luminous.")

    assert result["title"] == "The Last Marquee"
    assert result["tagline"] == "Every light hides a memory."
    assert "Make it luminous." in prompts[0][0]
    assert prompts[0][1] == 4


def test_a2a_message_send_returns_movie_json(monkeypatch) -> None:
    """Verify the A2A JSON-RPC surface returns structured movie text."""

    def fake_run_writer_agent(brief: str) -> dict[str, str]:
        assert brief == "Write a moonlit adventure."
        return {
            "title": "Moon Harbor",
            "tagline": "The tide remembers.",
            "synopsis": "A sailor follows silver maps across a sleeping sea.",
            "genre": "adventure",
            "visual_style": "moonlit ocean, silver-blue palette",
        }

    monkeypatch.setattr(
        "writer_agent.a2a_server.run_writer_agent", fake_run_writer_agent
    )

    response = _handle_json_rpc_request(
        {
            "jsonrpc": "2.0",
            "id": "request-1",
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [{"kind": "text", "text": "Write a moonlit adventure."}],
                }
            },
        }
    )

    result = response["result"]
    assert isinstance(result, dict)
    parts = result["parts"]
    assert isinstance(parts, list)
    movie = json.loads(parts[0]["text"])
    assert movie["title"] == "Moon Harbor"
    assert parts[0]["metadata"] == {"mimeType": "application/json"}


def _install_fake_agent_dependencies(
    monkeypatch,
    *,
    agent: type | None = None,
    runner: type | None = None,
) -> None:
    if agent is None:

        class _FakeAgent:
            def __init__(self, **kwargs: Any) -> None:
                _ = kwargs

        agent = _FakeAgent

    if runner is None:

        class _FakeRunner:
            @staticmethod
            def run_sync(agent: object, prompt: str, max_turns: int) -> SimpleNamespace:
                _ = agent
                _ = prompt
                _ = max_turns
                return SimpleNamespace(
                    final_output=json.dumps(
                        {
                            "title": "The Last Marquee",
                            "tagline": "Every light hides a memory.",
                            "synopsis": (
                                "A projectionist discovers a city inside old "
                                "film reels."
                            ),
                            "genre": "fantasy mystery",
                            "visual_style": (
                                "noir cinema glow with surreal architecture"
                            ),
                        }
                    )
                )

        runner = _FakeRunner

    fake_agents_module = SimpleNamespace(
        Agent=agent,
        Runner=runner,
    )
    monkeypatch.setitem(sys.modules, "agents", fake_agents_module)
