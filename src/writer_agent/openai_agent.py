"""AI agent that writes structured movie concepts."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents import Agent

_DEFAULT_MODEL = "gpt-4.1-mini"
_WRITER_PROMPT_TEMPLATE = """
Create one original movie concept for a poster-generation workflow.

Creative brief:
{brief}

Return only a JSON object with these exact string fields:
- title
- tagline
- synopsis
- genre
- visual_style

The synopsis should be one paragraph. The visual_style field should describe
the mood, composition, color palette, and key visual subject for a single
poster illustration.
"""
_REQUIRED_MOVIE_FIELDS = (
    "title",
    "tagline",
    "synopsis",
    "genre",
    "visual_style",
)


def create_writer_agent(model: str = _DEFAULT_MODEL) -> Agent:
    """Create the Writer Agent movie concept generator."""
    from agents import Agent

    return Agent(
        name="Movie Concept Writer",
        model=model,
        instructions=(
            "You create concise, original movie concepts for downstream "
            "illustration and poster agents. Always return only valid JSON "
            "matching the requested schema."
        ),
    )


def run_writer_agent(
    brief: str = "Create an original movie concept for a striking poster.",
    model: str = _DEFAULT_MODEL,
) -> dict[str, str]:
    """Run the Writer Agent and return validated movie details."""
    from agents import Runner

    prompt = _WRITER_PROMPT_TEMPLATE.format(brief=brief.strip())
    result = Runner.run_sync(create_writer_agent(model), prompt, max_turns=4)
    return _read_movie_details(str(result.final_output))


def _read_movie_details(text: str) -> dict[str, str]:
    data = json.loads(_extract_json_object(text))
    if not isinstance(data, dict):
        raise ValueError("Writer Agent returned a non-object JSON value.")

    movie: dict[str, str] = {}
    for field in _REQUIRED_MOVIE_FIELDS:
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Writer Agent omitted required field: {field}")
        movie[field] = value.strip()

    return movie


def _extract_json_object(text: str) -> str:
    stripped_text = text.strip()
    if stripped_text.startswith("{") and stripped_text.endswith("}"):
        return stripped_text

    start_index = stripped_text.find("{")
    end_index = stripped_text.rfind("}")
    if start_index == -1 or end_index == -1 or end_index < start_index:
        raise ValueError("Writer Agent did not return a JSON object.")

    return stripped_text[start_index : end_index + 1]
