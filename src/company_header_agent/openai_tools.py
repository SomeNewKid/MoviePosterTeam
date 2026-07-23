"""OpenAI Agents SDK adapters for company header agent tools."""

from __future__ import annotations

from agents import function_tool

from .tools import get_company_name, inject_company_header

get_company_name_tool = function_tool(get_company_name)
inject_company_header_tool = function_tool(inject_company_header)
