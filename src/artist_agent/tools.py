"""Tools used by the Artist Agent."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from typing import Any

_MCP_SIDECAR_URL_ENVIRONMENT_VARIABLE = "MCP_SIDECAR_URL"
_MCP_GENERATE_IMAGE_TOOL_NAME = "generate_image"


def generate_image(prompt: str, image_reference_base64: str | None = None) -> str:
    """Generate an image through the MCP sidecar."""
    arguments: dict[str, object] = {"prompt": prompt}
    if image_reference_base64 is not None:
        arguments["image_reference_base64"] = image_reference_base64

    return _call_mcp_sidecar_tool(_MCP_GENERATE_IMAGE_TOOL_NAME, arguments)


def _call_mcp_sidecar_tool(tool_name: str, arguments: Mapping[str, object]) -> str:
    import anyio

    sidecar_url = _get_mcp_sidecar_url()
    return anyio.run(_call_mcp_tool_async, sidecar_url, tool_name, arguments)


def _get_mcp_sidecar_url() -> str:
    sidecar_url = os.environ.get(_MCP_SIDECAR_URL_ENVIRONMENT_VARIABLE)
    if not sidecar_url:
        raise RuntimeError("MCP_SIDECAR_URL is not configured.")

    return sidecar_url


async def _call_mcp_tool_async(
    sidecar_url: str,
    tool_name: str,
    arguments: Mapping[str, object],
) -> str:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client

    async with streamablehttp_client(sidecar_url) as (
        read_stream,
        write_stream,
        _get_session_id,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, dict(arguments))

    return _read_mcp_tool_text_result(result)


def _read_mcp_tool_text_result(result: Any) -> str:
    structured_content = getattr(result, "structuredContent", None)
    if isinstance(structured_content, dict):
        value = structured_content.get("result")
        if isinstance(value, str):
            return value
        if value is not None:
            return json.dumps(value, indent=2)
        return json.dumps(structured_content, indent=2)

    content_blocks = getattr(result, "content", ())
    for block in content_blocks:
        text = getattr(block, "text", None)
        if isinstance(text, str):
            return text

    raise RuntimeError("MCP tool did not return a text result.")
