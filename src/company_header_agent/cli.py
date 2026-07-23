"""Command-line interface for the company header agent."""

from __future__ import annotations

import argparse
import sys

from company_header_agent.a2a_server import run_server
from company_header_agent.openai_agent import run_company_header_agent


def main(argv: list[str] | None = None) -> int:
    """Run the company header agent CLI."""
    arguments = _parse_arguments(argv)
    if arguments.serve:
        run_server(
            host=arguments.host,
            port=arguments.port,
            model=arguments.model,
            public_base_url=arguments.public_base_url,
        )
        return 0

    html_document = sys.stdin.read()
    updated_html_document = run_company_header_agent(
        html_document,
        model=arguments.model,
    )
    print(updated_html_document)
    return 0


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inject a company header into an HTML document."
    )
    parser.add_argument(
        "--model",
        default="gpt-4.1-mini",
        help="OpenAI model used by the company header agent.",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Run the company header agent as an A2A HTTP server.",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="Host interface for A2A server mode.",
    )
    parser.add_argument(
        "--port",
        default=8080,
        type=int,
        help="Port for A2A server mode.",
    )
    parser.add_argument(
        "--public-base-url",
        default=None,
        help="Base URL advertised in the A2A Agent Card.",
    )
    return parser.parse_args(argv)
