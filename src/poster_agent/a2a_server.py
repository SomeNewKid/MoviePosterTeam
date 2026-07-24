"""Small A2A-compatible HTTP server for the Poster Agent."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from a2a_support.server import (
    build_agent_card,
    json_rpc_error,
    json_rpc_text_result,
    read_json_request,
    read_message_text,
    write_json_response,
)

from .openai_agent import run_poster_agent

_AGENT_NAME = "Poster Agent"
_DEFAULT_POSTER_REQUEST = (
    '{"movie": {"title": "Moon Harbor", "tagline": "The tide remembers.", '
    '"synopsis": "A sailor follows silver maps across a sleeping sea.", '
    '"genre": "adventure", '
    '"visual_style": "moonlit ocean, silver-blue palette"}, '
    '"illustration": {"artifact_path": "artist_agent/illustration.png"}}'
)


def serve_poster_agent(host: str, port: int, public_base_url: str) -> None:
    """Serve the Poster Agent over a small JSON-RPC HTTP surface."""
    handler = _build_handler(public_base_url.rstrip("/"))
    server = ThreadingHTTPServer((host, port), handler)
    server.serve_forever()


def _build_handler(public_base_url: str) -> type[BaseHTTPRequestHandler]:
    class _PosterAgentHandler(BaseHTTPRequestHandler):
        server_version = "PosterAgentA2A/1.0"

        def do_GET(self) -> None:
            """Handle health and Agent Card requests."""
            if self.path == "/health":
                write_json_response(self, {"status": "ok"})
                return
            if self.path == "/.well-known/agent.json":
                write_json_response(self, _build_agent_card(public_base_url))
                return

            self.send_error(404, "Not found")

        def do_POST(self) -> None:
            """Handle JSON-RPC message/send requests."""
            if self.path != "/a2a":
                self.send_error(404, "Not found")
                return

            try:
                request = read_json_request(self)
                response = _handle_json_rpc_request(request)
            except Exception as error:
                response = json_rpc_error(None, -32000, str(error))

            write_json_response(self, response)

        def log_message(self, format: str, *args: object) -> None:
            """Keep supporting-agent logs focused on explicit application output."""
            _ = format
            _ = args

    return _PosterAgentHandler


def _build_agent_card(public_base_url: str) -> dict[str, object]:
    return build_agent_card(
        name=_AGENT_NAME,
        description="Composes a final movie poster from movie JSON and artwork.",
        public_base_url=public_base_url,
        skills=[
            {
                "id": "compose_movie_poster",
                "name": "Compose Movie Poster",
                "description": (
                    "Return shared artifact metadata for a final poster image."
                ),
            }
        ],
    )


def _handle_json_rpc_request(request: dict[str, object]) -> dict[str, object]:
    request_id = request.get("id")
    if request.get("method") != "message/send":
        return json_rpc_error(request_id, -32601, "Unsupported method.")

    poster_request = read_message_text(request.get("params"))
    poster = run_poster_agent(poster_request or _DEFAULT_POSTER_REQUEST)
    return json_rpc_text_result(
        request_id,
        json.dumps(poster, sort_keys=True),
        mime_type="application/json",
    )
