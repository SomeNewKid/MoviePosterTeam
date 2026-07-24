"""Command-line interface for the Writer Agent."""

from __future__ import annotations

import argparse
import json

from .a2a_server import serve_writer_agent
from .openai_agent import run_writer_agent


def main(argv: list[str] | None = None) -> int:
    """Run the Writer Agent CLI or A2A service."""
    arguments = _parse_arguments(argv)
    if arguments.serve:
        serve_writer_agent(
            host=arguments.host,
            port=arguments.port,
            public_base_url=arguments.public_base_url,
        )
        return 0

    movie = run_writer_agent(arguments.brief)
    print(json.dumps(movie, sort_keys=True))
    return 0


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Writer Agent.")
    parser.add_argument("--serve", action="store_true", help="Start the A2A server.")
    parser.add_argument("--host", default="127.0.0.1", help="A2A bind host.")
    parser.add_argument("--port", type=int, default=8080, help="A2A bind port.")
    parser.add_argument(
        "--public-base-url",
        default="http://writer-agent:8080",
        help="Public base URL advertised in the Agent Card.",
    )
    parser.add_argument(
        "--brief",
        default="Create an original movie concept for a striking poster.",
        help="Creative brief for the movie concept.",
    )
    return parser.parse_args(argv)
