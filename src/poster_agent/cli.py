"""Command-line interface for the Poster Agent."""

from __future__ import annotations

import argparse
import json

from .a2a_server import serve_poster_agent
from .openai_agent import run_poster_agent


def main(argv: list[str] | None = None) -> int:
    """Run the Poster Agent CLI or A2A service."""
    arguments = _parse_arguments(argv)
    if arguments.serve:
        serve_poster_agent(
            host=arguments.host,
            port=arguments.port,
            public_base_url=arguments.public_base_url,
        )
        return 0

    poster = run_poster_agent(arguments.poster_request)
    print(json.dumps(poster, sort_keys=True))
    return 0


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Poster Agent.")
    parser.add_argument("--serve", action="store_true", help="Start the A2A server.")
    parser.add_argument("--host", default="127.0.0.1", help="A2A bind host.")
    parser.add_argument("--port", type=int, default=8080, help="A2A bind port.")
    parser.add_argument(
        "--public-base-url",
        default="http://poster-agent:8080",
        help="Public base URL advertised in the Agent Card.",
    )
    parser.add_argument(
        "--poster-request",
        default=(
            '{"movie": {"title": "Moon Harbor", '
            '"tagline": "The tide remembers.", '
            '"synopsis": "A sailor follows silver maps across a sleeping sea.", '
            '"genre": "adventure", '
            '"visual_style": "moonlit ocean, silver-blue palette"}, '
            '"illustration": {"artifact_path": "artist_agent/illustration.png"}}'
        ),
        help="Poster request JSON with movie details and illustration artifact.",
    )
    return parser.parse_args(argv)
