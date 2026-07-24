"""Tests for the Poster Agent package."""

from __future__ import annotations

import base64
import json

from poster_agent.a2a_server import _handle_json_rpc_request
from poster_agent.openai_agent import run_poster_agent


def test_run_poster_agent_uses_illustration_reference(
    tmp_path,
    monkeypatch,
) -> None:
    """Verify Poster Agent composes a poster from a shared illustration."""
    shared_path = tmp_path / "shared"
    illustration_path = shared_path / "artist_agent" / "illustration.png"
    illustration_path.parent.mkdir(parents=True)
    illustration_path.write_bytes(b"illustration bytes")
    calls = []

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

    monkeypatch.setenv("SANDBOX_SHARED_DIR", str(shared_path))
    monkeypatch.setattr("poster_agent.openai_agent.generate_image", fake_generate_image)

    result = run_poster_agent(_poster_request_json())

    assert result["success"] is True
    assert result["artifact_path"] == "poster_agent/poster.png"
    assert result["file_name"] == "poster.png"
    assert result["byte_count"] == 12
    assert result["illustration_reference_path"] == "artist_agent/illustration.png"
    assert "complete vertical theatrical movie poster" in calls[0][0]
    assert "Moon Harbor" in calls[0][0]
    assert "The tide remembers." in calls[0][0]
    assert calls[0][1] == base64.b64encode(b"illustration bytes").decode("ascii")
    assert (shared_path / "poster_agent" / "poster.png").read_bytes() == (
        b"poster bytes"
    )


def test_a2a_message_send_returns_poster_json(monkeypatch) -> None:
    """Verify the Poster Agent A2A surface returns poster metadata text."""

    def fake_run_poster_agent(poster_request: str) -> dict[str, object]:
        request = json.loads(poster_request)
        assert request["movie"]["title"] == "Moon Harbor"
        return {
            "success": True,
            "artifact_path": "poster_agent/poster.png",
            "file_name": "poster.png",
            "mime_type": "image/png",
            "model": "gpt-image-1",
            "size": "1024x1024",
            "byte_count": 12,
            "prompt": "Create a poster for Moon Harbor.",
            "illustration_reference_path": "artist_agent/illustration.png",
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
                    "parts": [{"kind": "text", "text": _poster_request_json()}],
                }
            },
        }
    )

    result = response["result"]
    assert isinstance(result, dict)
    parts = result["parts"]
    assert isinstance(parts, list)
    poster = json.loads(parts[0]["text"])
    assert poster["artifact_path"] == "poster_agent/poster.png"
    assert "image_base64" not in poster
    assert parts[0]["metadata"] == {"mimeType": "application/json"}


def _poster_request_json() -> str:
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
                "artifact_path": "artist_agent/illustration.png",
            },
        }
    )
