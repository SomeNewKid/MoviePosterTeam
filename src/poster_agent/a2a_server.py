"""Small A2A-compatible HTTP server for the Poster Agent."""

from __future__ import annotations

import json
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from a2a_support.server import (
    build_agent_card,
    build_task,
    build_text_artifact,
    json_rpc_error,
    json_rpc_result,
    read_json_request,
    read_message_text,
    read_task_id,
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
_TASKS: dict[str, dict[str, object]] = {}
_TASK_LOCK = threading.Lock()


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
            """Handle JSON-RPC A2A requests."""
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
    method = request.get("method")
    if method == "message/send":
        return _handle_message_send(request)
    if method == "tasks/get":
        return _handle_tasks_get(request)

    return json_rpc_error(request_id, -32601, "Unsupported method.")


def _handle_message_send(request: dict[str, object]) -> dict[str, object]:
    request_id = request.get("id")
    poster_request = read_message_text(request.get("params"))
    task_id = f"poster-task-{uuid.uuid4()}"
    context_id = f"poster-context-{uuid.uuid4()}"
    task = build_task(
        task_id,
        context_id,
        "TASK_STATE_SUBMITTED",
        message_text="Poster composition task submitted.",
    )
    _set_task(task_id, task)

    thread = threading.Thread(
        target=_run_poster_task,
        args=(task_id, context_id, poster_request or _DEFAULT_POSTER_REQUEST),
        daemon=True,
    )
    thread.start()
    return json_rpc_result(request_id, task)


def _handle_tasks_get(request: dict[str, object]) -> dict[str, object]:
    request_id = request.get("id")
    task_id = read_task_id(request.get("params"))
    task = _get_task(task_id)
    if task is None:
        return json_rpc_error(request_id, -32001, f"Unknown task id: {task_id}")

    return json_rpc_result(request_id, task)


def _run_poster_task(task_id: str, context_id: str, poster_request: str) -> None:
    _set_task(
        task_id,
        build_task(
            task_id,
            context_id,
            "TASK_STATE_WORKING",
            message_text="Poster composition task is running.",
        ),
    )
    try:
        poster = run_poster_agent(poster_request)
    except Exception as error:
        _set_task(
            task_id,
            build_task(
                task_id,
                context_id,
                "TASK_STATE_FAILED",
                message_text=str(error),
            ),
        )
        return

    artifact = build_text_artifact(
        "movie-poster",
        "Movie poster metadata",
        json.dumps(poster, sort_keys=True),
        mime_type="application/json",
    )
    _set_task(
        task_id,
        build_task(
            task_id,
            context_id,
            "TASK_STATE_COMPLETED",
            message_text="Poster composition task completed.",
            artifacts=(artifact,),
        ),
    )


def _set_task(task_id: str, task: dict[str, object]) -> None:
    with _TASK_LOCK:
        _TASKS[task_id] = task


def _get_task(task_id: str) -> dict[str, object] | None:
    with _TASK_LOCK:
        task = _TASKS.get(task_id)
        if task is None:
            return None

        return json.loads(json.dumps(task))
