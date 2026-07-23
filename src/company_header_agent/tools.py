"""Tools used by the company header agent."""

from __future__ import annotations

import html
import os
from html.parser import HTMLParser
from typing import Any

_MCP_SIDECAR_URL_ENVIRONMENT_VARIABLE = "MCP_SIDECAR_URL"
_MCP_COMPANY_NAME_RESOURCE_URI = "mcp-sidecar://company/name.txt"


class _HtmlStartTagLocator(HTMLParser):
    def __init__(self, html_document: str) -> None:
        super().__init__(convert_charrefs=False)
        self._html_document = html_document
        self._line_offsets = _build_line_offsets(html_document)
        self.body_open_end: int | None = None
        self.first_main_start: int | None = None

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        del attrs
        offset = self._offset_from_position(self.getpos())
        if tag.lower() == "body" and self.body_open_end is None:
            starttag_text = self.get_starttag_text()
            if starttag_text is None:
                raise ValueError("HTML parser could not read the <body> start tag.")
            self.body_open_end = offset + len(starttag_text)
            return

        if (
            tag.lower() == "main"
            and self.body_open_end is not None
            and self.first_main_start is None
        ):
            self.first_main_start = offset

    def _offset_from_position(self, position: tuple[int, int]) -> int:
        line, column = position
        return self._line_offsets[line - 1] + column


def get_company_name() -> str:
    """Read the company name resource from the MCP sidecar."""
    sidecar_url = _get_mcp_sidecar_url()
    return _call_mcp_resource(sidecar_url, _MCP_COMPANY_NAME_RESOURCE_URI)


def inject_company_header(html_document: str, company_name: str) -> str:
    """Return an HTML document with a company header inserted into body."""
    locator = _HtmlStartTagLocator(html_document)
    locator.feed(html_document)
    if locator.body_open_end is None:
        raise ValueError("HTML document must contain a <body> element.")

    header = _build_company_header(company_name)
    insertion_offset = locator.first_main_start or locator.body_open_end
    return html_document[:insertion_offset] + header + html_document[insertion_offset:]


def _build_company_header(company_name: str) -> str:
    escaped_company_name = html.escape(company_name.strip())
    return f"\n<header>{escaped_company_name}</header>\n"


def _build_line_offsets(text: str) -> tuple[int, ...]:
    offsets = [0]
    for index, character in enumerate(text):
        if character == "\n":
            offsets.append(index + 1)

    return tuple(offsets)


def _get_mcp_sidecar_url() -> str:
    sidecar_url = os.environ.get(_MCP_SIDECAR_URL_ENVIRONMENT_VARIABLE)
    if not sidecar_url:
        raise RuntimeError("MCP_SIDECAR_URL is not configured.")

    return sidecar_url


def _call_mcp_resource(sidecar_url: str, resource_uri: str) -> str:
    import anyio

    return anyio.run(_call_mcp_resource_async, sidecar_url, resource_uri)


async def _call_mcp_resource_async(sidecar_url: str, resource_uri: str) -> str:
    from mcp import ClientSession
    from mcp.client.streamable_http import streamablehttp_client
    from pydantic import AnyUrl

    async with streamablehttp_client(sidecar_url) as (
        read_stream,
        write_stream,
        _get_session_id,
    ):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.read_resource(AnyUrl(resource_uri))

    return _read_mcp_resource_text_result(result)


def _read_mcp_resource_text_result(result: Any) -> str:
    contents = getattr(result, "contents", ())
    text_parts = [
        text
        for content in contents
        if isinstance((text := getattr(content, "text", None)), str)
    ]
    if text_parts:
        return "\n\n".join(text_parts)

    raise RuntimeError("MCP resource did not return text content.")
