"""Tests for the Poster Agent package."""

from __future__ import annotations

import base64
import json
import time

from poster_agent.a2a_server import _handle_json_rpc_request
from poster_agent.openai_agent import run_poster_agent


def test_run_poster_agent_uses_illustration_reference(
    monkeypatch,
) -> None:
    """Verify Poster Agent composes a poster from A2A image data."""
    calls = []
    image_reference = base64.b64encode(b"illustration bytes").decode("ascii")

    def fake_generate_image(prompt: str, image_reference_base64: str | None) -> str:
        calls.append((prompt, image_reference_base64))
        return json.dumps(
            {
                "image_base64": base64.b64encode(b"poster bytes").decode("ascii"),
                "mime_type": "image/png",
                "model": "gpt-image-1",
                "size": "1024x1024",
            }
        )

    monkeypatch.setattr("poster_agent.openai_agent.generate_image", fake_generate_image)

    result = run_poster_agent(_poster_request_json(image_reference))

    assert result["success"] is True
    assert result["file_name"] == "poster.png"
    assert result["image_base64"] == base64.b64encode(b"poster bytes").decode("ascii")
    assert result["byte_count"] == 12
    assert result["illustration_reference"] == "image_reference_base64"
    assert "complete vertical theatrical movie poster" in calls[0][0]
    assert "Moon Harbor" in calls[0][0]
    assert "The tide remembers." in calls[0][0]
    assert calls[0][1] == image_reference


def test_a2a_message_send_returns_poster_json(monkeypatch) -> None:
    """Verify the Poster Agent A2A surface completes a poster task."""

    def fake_run_poster_agent(poster_request: str) -> dict[str, object]:
        request = json.loads(poster_request)
        assert request["movie"]["title"] == "Moon Harbor"
        return {
            "success": True,
            "file_name": "poster.png",
            "image_base64": base64.b64encode(b"poster bytes").decode("ascii"),
            "mime_type": "image/png",
            "model": "gpt-image-1",
            "size": "1024x1024",
            "byte_count": 12,
            "prompt": "Create a poster for Moon Harbor.",
            "illustration_reference": "image_reference_base64",
        }

    monkeypatch.setattr(
        "poster_agent.a2a_server.run_poster_agent",
        fake_run_poster_agent,
    )

    response = _handle_json_rpc_request(
        {
            "jsonrpc": "2.0",
            "id": "request-1",
            "method": "message/send",
            "params": {
                "message": {
                    "role": "user",
                    "parts": [
                        {
                            "kind": "text",
                            "text": _poster_request_json(
                                base64.b64encode(b"illustration bytes").decode("ascii")
                            ),
                        }
                    ],
                }
            },
        }
    )

    result = response["result"]
    assert isinstance(result, dict)
    assert result["kind"] == "task"
    status = result["status"]
    assert isinstance(status, dict)
    assert status["state"] == "TASK_STATE_SUBMITTED"
    task_id = result["id"]
    assert isinstance(task_id, str)

    for _ in range(50):
        task_response = _handle_json_rpc_request(
            {
                "jsonrpc": "2.0",
                "id": "request-2",
                "method": "tasks/get",
                "params": {
                    "id": task_id,
                    "historyLength": 0,
                },
            }
        )
        task = task_response["result"]
        assert isinstance(task, dict)
        status = task["status"]
        assert isinstance(status, dict)
        if status["state"] == "TASK_STATE_COMPLETED":
            break
        time.sleep(0.01)
    else:
        raise AssertionError("Poster task did not complete.")

    artifacts = task["artifacts"]
    assert isinstance(artifacts, list)
    artifact = artifacts[0]
    assert isinstance(artifact, dict)
    parts = artifact["parts"]
    assert isinstance(parts, list)
    part = parts[0]
    assert isinstance(part, dict)
    poster = json.loads(part["text"])
    assert poster["file_name"] == "poster.png"
    assert poster["image_base64"] == base64.b64encode(b"poster bytes").decode("ascii")
    assert part["metadata"] == {"mimeType": "application/json"}


def test_a2a_tasks_get_rejects_unknown_task_id() -> None:
    """Verify unknown Poster Agent tasks return a JSON-RPC error."""
    response = _handle_json_rpc_request(
        {
            "jsonrpc": "2.0",
            "id": "request-3",
            "method": "tasks/get",
            "params": {
                "id": "missing-task",
            },
        }
    )

    error = response["error"]
    assert isinstance(error, dict)
    assert error["code"] == -32001


def _poster_request_json(image_reference_base64: str) -> str:
    return json.dumps(
        {
            "movie": {
                "title": "Moon Harbor",
                "tagline": "The tide remembers.",
                "synopsis": "A sailor follows silver maps across a sleeping sea.",
                "genre": "adventure",
                "visual_style": "moonlit ocean, silver-blue palette",
            },
            "illustration": {
                "file_name": "illustration.png",
            },
            "image_reference_base64": image_reference_base64,
        }
    )
