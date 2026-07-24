"""Command-line interface for the Artist Agent."""

from __future__ import annotations

import argparse
import json

from .a2a_server import serve_artist_agent
from .openai_agent import run_artist_agent


def main(argv: list[str] | None = None) -> int:
    """Run the Artist Agent CLI or A2A service."""
    arguments = _parse_arguments(argv)
    if arguments.serve:
        serve_artist_agent(
            host=arguments.host,
            port=arguments.port,
            public_base_url=arguments.public_base_url,
        )
        return 0

    illustration = run_artist_agent(arguments.movie_details)
    print(json.dumps(illustration, sort_keys=True))
    return 0


def _parse_arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Artist Agent.")
    parser.add_argument("--serve", action="store_true", help="Start the A2A server.")
    parser.add_argument("--host", default="127.0.0.1", help="A2A bind host.")
    parser.add_argument("--port", type=int, default=8080, help="A2A bind port.")
    parser.add_argument(
        "--public-base-url",
        default="http://artist-agent:8080",
        help="Public base URL advertised in the Agent Card.",
    )
    parser.add_argument(
        "--movie-details",
        default=(
            '{"title": "Moon Harbor", "tagline": "The tide remembers.", '
            '"synopsis": "A sailor follows silver maps across a sleeping sea.", '
            '"genre": "adventure", '
            '"visual_style": "moonlit ocean, silver-blue palette"}'
        ),
        help="Movie details JSON used to generate the illustration.",
    )
    return parser.parse_args(argv)
