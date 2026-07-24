"""Tests for shared A2A support helpers."""

from __future__ import annotations

import pytest

from a2a_support.client import read_agent_endpoint_url, read_message_text_result
from a2a_support.server import (
    build_agent_card,
    json_rpc_error,
    json_rpc_text_result,
    read_message_text,
)


def test_build_agent_card_uses_public_a2a_endpoint() -> None:
    """Verify Agent Cards expose the JSON-RPC endpoint URL."""
    card = build_agent_card(
        name="Writer Agent",
        description="Writes movie concepts.",
        public_base_url="http://writer-agent:8080/",
        skills=[{"id": "write_movie_concept"}],
    )

    assert card["name"] == "Writer Agent"
    assert card["url"] == "http://writer-agent:8080/a2a"
    assert card["skills"] == [{"id": "write_movie_concept"}]


def test_read_message_text_joins_text_parts() -> None:
    """Verify JSON-RPC message text parts are read in order."""
    text = read_message_text(
        {
            "message": {
                "parts": [
                    {"kind": "text", "text": "First"},
                    {"kind": "data", "data": {"ignored": True}},
                    {"kind": "text", "text": "Second"},
                ]
            }
        }
    )

    assert text == "First\n\nSecond"


def test_json_rpc_text_result_can_be_read_by_client_helper() -> None:
    """Verify server text results match the shared client reader."""
    response = json_rpc_text_result(
        request_id="request-1",
        text='{"title": "Moon Harbor"}',
        mime_type="application/json",
    )

    assert read_message_text_result(response["result"]) == '{"title": "Moon Harbor"}'


def test_json_rpc_error_uses_standard_error_shape() -> None:
    """Verify JSON-RPC error responses carry code and message."""
    response = json_rpc_error("request-1", -32601, "Unsupported method.")

    assert response == {
        "jsonrpc": "2.0",
        "id": "request-1",
        "error": {
            "code": -32601,
            "message": "Unsupported method.",
        },
    }


def test_read_agent_endpoint_url_requires_url() -> None:
    """Verify Agent Cards must include a usable endpoint URL."""
    with pytest.raises(RuntimeError, match="must include a URL"):
        read_agent_endpoint_url({})


def test_read_message_text_result_requires_text_part() -> None:
    """Verify client parsing fails closed when no text part is present."""
    with pytest.raises(RuntimeError, match="did not contain text"):
        read_message_text_result({"parts": [{"kind": "data", "data": {}}]})
