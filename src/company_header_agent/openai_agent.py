"""AI agent that injects a company header into an HTML document."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents import Agent

_DEFAULT_MODEL = "gpt-4.1-mini"
_AGENT_PROMPT_TEMPLATE = """
You will receive one complete HTML document.

Use the get_company_name tool first to read the company_name MCP resource.
Then use the inject_company_header tool with the original HTML document and the
company name. Return only the updated HTML document from the tool result. Do not
wrap the HTML in Markdown, commentary, or code fences.

HTML document:
{html_document}
"""


def create_openai_agent(model: str = _DEFAULT_MODEL) -> Agent:
    """Create the company header HTML update agent."""
    from agents import Agent

    from .openai_tools import get_company_name_tool, inject_company_header_tool

    return Agent(
        name="Company Header HTML Updater",
        model=model,
        instructions=(
            "You update an existing HTML document by adding a company header. "
            "Always read the company name from the MCP resource tool, always "
            "use the HTML injection tool for the mutation, and return only the "
            "updated HTML document."
        ),
        tools=[
            get_company_name_tool,
            inject_company_header_tool,
        ],
    )


def run_company_header_agent(
    html_document: str,
    model: str = _DEFAULT_MODEL,
) -> str:
    """Run the company header agent and return the updated HTML document."""
    from agents import Runner

    result = Runner.run_sync(
        create_openai_agent(model),
        _AGENT_PROMPT_TEMPLATE.format(html_document=html_document),
        max_turns=6,
    )
    return str(result.final_output)
