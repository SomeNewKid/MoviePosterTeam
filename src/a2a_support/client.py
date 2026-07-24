"""Client helpers for small A2A HTTP integrations."""

from __future__ import annotations

import json
import urllib.request
from typing import Any


def read_agent_card(base_url: str, timeout: int = 10) -> dict[str, object]:
    """Read an A2A Agent Card from a base URL."""
    card_url = f"{base_url.rstrip('/')}/.well-known/agent.json"
    with _urlopen_no_proxy(card_url, timeout=timeout) as response:
        data = json.loads(response.read().decode("utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("A2A Agent Card must be a JSON object.")

    return data


def read_agent_endpoint_url(agent_card: dict[str, object]) -> str:
    """Read the JSON-RPC endpoint URL from an A2A Agent Card."""
    endpoint_url = agent_card.get("url")
    if not isinstance(endpoint_url, str) or not endpoint_url.strip():
        raise RuntimeError("A2A Agent Card must include a URL.")

    return endpoint_url.strip()


def send_text_message(
    endpoint_url: str,
    text: str,
    request_id: str = "a2a-message-request",
    timeout: int = 60,
) -> str:
    """Send a JSON-RPC message/send text request and return the response text."""
    request_body = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [
                    {
                        "kind": "text",
                        "text": text,
                    }
                ],
            }
        },
    }
    request = urllib.request.Request(
        endpoint_url,
        data=json.dumps(request_body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with _urlopen_no_proxy(request, timeout=timeout) as response:
        response_data = json.loads(response.read().decode("utf-8"))
    if not isinstance(response_data, dict):
        raise RuntimeError("A2A response must be a JSON object.")
    if "error" in response_data:
        raise RuntimeError(f"A2A error: {response_data['error']}")

    return read_message_text_result(response_data.get("result"))


def read_message_text_result(result: object) -> str:
    """Read the first text part from a JSON-RPC message result."""
    if not isinstance(result, dict):
        raise RuntimeError("A2A result must be an object.")

    parts = result.get("parts")
    if not isinstance(parts, list):
        raise RuntimeError("A2A result did not contain parts.")

    for part in parts:
        if isinstance(part, dict) and isinstance(part.get("text"), str):
            return str(part["text"])

    raise RuntimeError("A2A result did not contain text.")


def _urlopen_no_proxy(
    url: str | urllib.request.Request,
    timeout: int,
) -> Any:
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return opener.open(url, timeout=timeout)
