"""Tests for the Artist Agent package."""

from __future__ import annotations

import json
import time

from artist_agent.a2a_server import _handle_json_rpc_request
from artist_agent.openai_agent import run_artist_agent


def test_run_artist_agent_returns_a2a_image_artifact_from_movie_json(
    monkeypatch,
) -> None:
    """Verify Artist Agent returns generated image data as A2A metadata."""
    calls = []

    def fake_generate_image(prompt: str) -> str:
        calls.append(prompt)
        return json.dumps(
            {
                "image_base64": "aW1hZ2U=",
                "mime_type": "image/png",
                "model": "gpt-image-1",
                "size": "1024x1024",
            }
        )

    monkeypatch.setattr("artist_agent.openai_agent.generate_image", fake_generate_image)

    result = run_artist_agent(
        json.dumps(
            {
                "title": "Moon Harbor",
                "tagline": "The tide remembers.",
                "synopsis": "A sailor follows silver maps across a sleeping sea.",
                "genre": "adventure",
                "visual_style": "moonlit ocean, silver-blue palette",
            }
        )
    )

    assert result["success"] is True
    assert result["file_name"] == "illustration.png"
    assert result["image_base64"] == "aW1hZ2U="
    assert result["mime_type"] == "image/png"
    assert result["model"] == "gpt-image-1"
    assert result["size"] == "1024x1024"
    assert result["byte_count"] == 5
    assert result["prompt"] == calls[0]
    assert "Moon Harbor" in calls[0]
    assert "Do not include typography" in calls[0]


def test_a2a_message_send_returns_illustration_json(monkeypatch) -> None:
    """Verify the Artist Agent A2A surface completes an illustration task."""

    def fake_run_artist_agent(movie_details: str) -> dict[str, object]:
        movie = json.loads(movie_details)
        assert movie["title"] == "Moon Harbor"
        return {
            "success": True,
            "file_name": "illustration.png",
            "image_base64": "aW1hZ2U=",
            "mime_type": "image/png",
            "model": "gpt-image-1",
            "size": "1024x1024",
            "byte_count": 5,
            "prompt": "Create an illustration for Moon Harbor.",
        }

    monkeypatch.setattr(
        "artist_agent.a2a_server.run_artist_agent",
        fake_run_artist_agent,
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
                            "text": json.dumps({"title": "Moon Harbor"}),
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
        raise AssertionError("Artist task did not complete.")

    artifacts = task["artifacts"]
    assert isinstance(artifacts, list)
    artifact = artifacts[0]
    assert isinstance(artifact, dict)
    parts = artifact["parts"]
    assert isinstance(parts, list)
    part = parts[0]
    assert isinstance(part, dict)
    illustration = json.loads(part["text"])
    assert illustration["file_name"] == "illustration.png"
    assert illustration["image_base64"] == "aW1hZ2U="
    assert part["metadata"] == {"mimeType": "application/json"}


def test_a2a_tasks_get_rejects_unknown_task_id() -> None:
    """Verify unknown Artist Agent tasks return a JSON-RPC error."""
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
