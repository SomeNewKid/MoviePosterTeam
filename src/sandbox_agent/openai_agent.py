"""AI agent that builds a simple HTML document through declared tools."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agents import Agent

_OUTPUT_DIRECTORY = Path("/sandbox-output")
_SITE_DIRECTORY = _OUTPUT_DIRECTORY / "site"
_DEFAULT_MODEL = "gpt-4.1-mini"
_AGENT_PROMPT = """
Create a small movie-poster preview page named index.html, one generated
illustration image named illustration.png, and one final movie poster image
named poster.png.

Use the get_movie_details tool first. Ask for an original movie concept suitable
for a dramatic illustrated poster. Treat the response as a JSON object with
title, tagline, synopsis, genre, and visual_style fields.

Call the get_movie_illustration tool exactly once with the movie details JSON.
Treat the response as a JSON object with artifact_path, mime_type, model, size,
byte_count, and prompt fields. Copy the artifact_path value to illustration.png
with the save_shared_image_artifact tool. Do not call generate_image,
generate_image_artifact, or save_image directly.

Call the get_movie_poster tool exactly once with a JSON object containing two
fields: movie, set to the movie details object, and illustration, set to the
illustration metadata object returned by get_movie_illustration. Treat the
response as a JSON object with artifact_path, mime_type, model, size, byte_count,
prompt, and illustration_reference_path fields. Copy the artifact_path value to
poster.png with the save_shared_image_artifact tool.

Build a friendly, self-contained page that references illustration.png with an
<img> element, references poster.png with another <img> element, and presents
the movie title, tagline, genre, synopsis, visual style, artist illustration
prompt, and poster composition prompt. Use embedded CSS in a <style> block so
the page is readable and pleasant, but keep the design simple.

Save the finished HTML document with the save_html_document tool. After saving
index.html, illustration.png, and poster.png, save a short status message with
the save_answer tool. The status message should say which files were created and
which movie title was used.
"""


def create_openai_agent(model: str = _DEFAULT_MODEL) -> Agent:
    """Create the Sandbox Agent HTML document generator."""
    from agents import Agent

    from .openai_tools import (
        get_movie_details_tool,
        get_movie_illustration_tool,
        get_movie_poster_tool,
        save_answer_tool,
        save_html_document_tool,
        save_shared_image_artifact_tool,
    )

    return Agent(
        name="Active Items Document Generator",
        model=model,
        instructions=(
            "You are a careful web page builder. Use the provided tools to "
            "retrieve structured movie details, request one illustration, "
            "request one final poster, save exactly two image files, save "
            "exactly one HTML file, and save the final status message. Do not "
            "finish until all seven "
            "tool calls have succeeded."
        ),
        tools=[
            get_movie_details_tool,
            get_movie_illustration_tool,
            get_movie_poster_tool,
            save_shared_image_artifact_tool,
            save_html_document_tool,
            save_answer_tool,
        ],
    )


def run_html_element_agent(model: str = _DEFAULT_MODEL) -> str:
    """Run the HTML element agent and save its final response."""
    from agents import Runner

    _SITE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    result = Runner.run_sync(
        create_openai_agent(model),
        _AGENT_PROMPT,
        max_turns=14,
    )
    return str(result.final_output)
