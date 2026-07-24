"""Tests for the Artist Agent package."""

from __future__ import annotations

import json

from artist_agent.a2a_server import _handle_json_rpc_request
from artist_agent.openai_agent import run_artist_agent


def test_run_artist_agent_writes_shared_artifact_from_movie_json(
    tmp_path,
    monkeypatch,
) -> None:
    """Verify Artist Agent turns movie details into a shared image artifact."""
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
    monkeypatch.setenv("SANDBOX_SHARED_DIR", str(tmp_path / "shared"))

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
    assert result["artifact_path"] == "artist_agent/illustration.png"
    assert result["file_name"] == "illustration.png"
    assert result["mime_type"] == "image/png"
    assert result["model"] == "gpt-image-1"
    assert result["size"] == "1024x1024"
    assert result["byte_count"] == 5
    assert result["prompt"] == calls[0]
    assert "Moon Harbor" in calls[0]
    assert "Do not include typography" in calls[0]
    assert (tmp_path / "shared" / "artist_agent" / "illustration.png").read_bytes() == (
        b"image"
    )


def test_a2a_message_send_returns_illustration_json(monkeypatch) -> None:
    """Verify the Artist Agent A2A surface returns illustration text."""

    def fake_run_artist_agent(movie_details: str) -> dict[str, object]:
        movie = json.loads(movie_details)
        assert movie["title"] == "Moon Harbor"
        return {
            "success": True,
            "artifact_path": "artist_agent/illustration.png",
            "file_name": "illustration.png",
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
    parts = result["parts"]
    assert isinstance(parts, list)
    illustration = json.loads(parts[0]["text"])
    assert illustration["artifact_path"] == "artist_agent/illustration.png"
    assert "image_base64" not in illustration
    assert parts[0]["metadata"] == {"mimeType": "application/json"}
