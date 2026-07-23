"""A2A HTTP server for the company header agent."""

from __future__ import annotations

import json
import sys
import uuid
from collections.abc import Callable
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from company_header_agent.openai_agent import run_company_header_agent

_DEFAULT_HOST = "0.0.0.0"
_DEFAULT_PORT = 8080
_AGENT_CARD_PATH = "/.well-known/agent.json"
_A2A_PATH = "/a2a"
_JSONRPC_VERSION = "2.0"
_DEFAULT_MODEL = "gpt-4.1-mini"


def build_agent_card(
    base_url: str = f"http://company-header-agent:{_DEFAULT_PORT}",
) -> dict[str, object]:
    """Return the A2A Agent Card for this agent."""
    return {
        "name": "Company Header Agent",
        "description": (
            "Adds a company header to an HTML document using the company_name "
            "MCP resource."
        ),
        "url": f"{base_url.rstrip('/')}{_A2A_PATH}",
        "version": "0.1.0",
        "protocolVersion": "0.2.0",
        "capabilities": {
            "streaming": False,
            "pushNotifications": False,
        },
        "defaultInputModes": ["text/html", "text/plain"],
        "defaultOutputModes": ["text/html"],
        "skills": [
            {
                "id": "inject_company_header",
                "name": "Inject Company Header",
                "description": (
                    "Returns an HTML document with a <header> element inserted "
                    "as a child of <body> before the main content."
                ),
                "inputModes": ["text/html", "text/plain"],
                "outputModes": ["text/html"],
                "examples": [
                    "<html><body><main><p>Hello</p></main></body></html>",
                ],
            }
        ],
    }


def run_server(
    host: str = _DEFAULT_HOST,
    port: int = _DEFAULT_PORT,
    model: str = _DEFAULT_MODEL,
    public_base_url: str | None = None,
) -> None:
    """Serve A2A requests until the process exits."""
    handler = _build_handler(model, public_base_url or f"http://{host}:{port}")
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Company header A2A agent listening on {host}:{port}", flush=True)
    server.serve_forever()


def handle_jsonrpc_request(
    request: dict[str, object],
    run_agent: Callable[[str], str],
) -> dict[str, object]:
    """Handle one A2A JSON-RPC request."""
    request_id = request.get("id")
    method = request.get("method")
    if request.get("jsonrpc") != _JSONRPC_VERSION:
        return _jsonrpc_error(request_id, -32600, "Invalid JSON-RPC version.")
    if method != "message/send":
        return _jsonrpc_error(request_id, -32601, f"Unsupported method: {method}")

    try:
        html_document = _extract_html_document(request.get("params"))
        updated_html_document = run_agent(html_document)
    except Exception as error:
        return _jsonrpc_error(request_id, -32000, str(error))

    return {
        "jsonrpc": _JSONRPC_VERSION,
        "id": request_id,
        "result": _build_message_result(updated_html_document),
    }


def _build_handler(
    model: str,
    public_base_url: str,
) -> type[BaseHTTPRequestHandler]:
    class _CompanyHeaderA2AHandler(BaseHTTPRequestHandler):
        server_version = "CompanyHeaderA2A/0.1"

        def do_GET(self) -> None:
            """Serve health checks and the A2A Agent Card."""
            if self.path == "/health":
                self._write_json({"status": "ok"})
                return
            if self.path == _AGENT_CARD_PATH:
                self._write_json(build_agent_card(public_base_url))
                return

            self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            """Handle A2A JSON-RPC messages."""
            if self.path != _A2A_PATH:
                self.send_error(HTTPStatus.NOT_FOUND)
                return

            try:
                request = self._read_json_object()
            except Exception as error:
                self._write_json(
                    _jsonrpc_error(None, -32700, str(error)),
                    status=HTTPStatus.BAD_REQUEST,
                )
                return

            response = handle_jsonrpc_request(
                request,
                lambda html_document: run_company_header_agent(
                    html_document,
                    model=model,
                ),
            )
            self._write_json(response)

        def log_message(self, format: str, *args: object) -> None:
            """Write HTTP logs to stderr using the default server style."""
            sys.stderr.write(f"{self.address_string()} - {format % args}\n")

        def _read_json_object(self) -> dict[str, object]:
            content_length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(content_length)
            data = json.loads(body.decode("utf-8"))
            if not isinstance(data, dict):
                raise ValueError("request body must be a JSON object")

            return data

        def _write_json(
            self,
            data: dict[str, object],
            status: HTTPStatus = HTTPStatus.OK,
        ) -> None:
            body = json.dumps(data).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return _CompanyHeaderA2AHandler


def _extract_html_document(params: object) -> str:
    if not isinstance(params, dict):
        raise ValueError("message/send params must be an object.")

    direct_html = params.get("html_document")
    if isinstance(direct_html, str):
        return direct_html

    message = params.get("message")
    if not isinstance(message, dict):
        raise ValueError("message/send params must contain a message object.")

    parts = message.get("parts")
    if not isinstance(parts, list):
        raise ValueError("A2A message must contain a parts array.")

    text_parts = tuple(_read_text_part(part) for part in parts)
    html_parts = tuple(text for text in text_parts if text)
    if not html_parts:
        raise ValueError("A2A message did not contain any text content.")

    return "\n".join(html_parts)


def _read_text_part(part: object) -> str:
    if not isinstance(part, dict):
        return ""
    if isinstance(part.get("text"), str):
        return str(part["text"])

    data = part.get("data")
    if isinstance(data, str):
        return data
    if isinstance(data, dict) and isinstance(data.get("text"), str):
        return str(data["text"])

    return ""


def _build_message_result(updated_html_document: str) -> dict[str, object]:
    return {
        "kind": "message",
        "messageId": str(uuid.uuid4()),
        "role": "agent",
        "parts": [
            {
                "kind": "text",
                "text": updated_html_document,
                "metadata": {
                    "mimeType": "text/html",
                },
            }
        ],
    }


def _jsonrpc_error(
    request_id: object,
    code: int,
    message: str,
) -> dict[str, object]:
    return {
        "jsonrpc": _JSONRPC_VERSION,
        "id": request_id,
        "error": {
            "code": code,
            "message": message,
        },
    }
