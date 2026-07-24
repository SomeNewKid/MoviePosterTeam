"""Poster Agent workload that composes a final movie poster."""

from __future__ import annotations

import base64
import binascii
import json

from .tools import generate_image

_POSTER_FILE_NAME = "poster.png"
_REQUIRED_MOVIE_FIELDS = (
    "title",
    "tagline",
    "synopsis",
    "genre",
    "visual_style",
)


def run_poster_agent(poster_request: str) -> dict[str, object]:
    """Generate one final movie poster and return A2A artifact metadata."""
    movie, image_reference_base64 = _read_poster_request(poster_request)
    prompt = _build_poster_prompt(movie)
    result_text = generate_image(prompt, image_reference_base64)
    result = _read_generate_image_result(result_text)
    image_base64 = result.pop("image_base64")
    image_bytes = _decode_base64_image(image_base64)

    return {
        "success": True,
        "file_name": _POSTER_FILE_NAME,
        "image_base64": image_base64,
        "mime_type": result.get("mime_type", "image/png"),
        "model": result.get("model", ""),
        "size": result.get("size", ""),
        "byte_count": len(image_bytes),
        "prompt": prompt,
        "illustration_reference": "image_reference_base64",
    }


def _read_poster_request(text: str) -> tuple[dict[str, str], str]:
    data = json.loads(_extract_json_object(text))
    if not isinstance(data, dict):
        raise ValueError("Poster Agent received a non-object JSON value.")

    movie_value = data.get("movie")
    if not isinstance(movie_value, dict):
        raise ValueError("Poster Agent request omitted movie details.")
    movie = _read_movie_details(movie_value)

    image_reference_base64 = data.get("image_reference_base64")
    if not isinstance(image_reference_base64, str) or not image_reference_base64:
        raise ValueError("Poster Agent request omitted image_reference_base64.")

    return movie, image_reference_base64.strip()


def _read_movie_details(data: dict[object, object]) -> dict[str, str]:
    movie: dict[str, str] = {}
    for field in _REQUIRED_MOVIE_FIELDS:
        value = data.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Poster Agent movie details omitted field: {field}")
        movie[field] = value.strip()

    return movie


def _build_poster_prompt(movie: dict[str, str]) -> str:
    return (
        "Create a complete vertical theatrical movie poster image, using the "
        "provided reference illustration as the central visual artwork. The final "
        "image should look like a finished movie poster, not only concept art. "
        f"Prominently include the movie name exactly as: {movie['title']}. "
        f"Include the tagline exactly as: {movie['tagline']}. "
        "Add tasteful poster typography, billing-block-style credits, release "
        "details, atmospheric layout, and graphic design elements that emulate a "
        "real cinema one-sheet. Keep the supplied illustration's main scene and "
        "mood recognizable while integrating it into the poster composition. "
        f"Genre: {movie['genre']}. "
        f"Synopsis context: {movie['synopsis']} "
        f"Visual style direction: {movie['visual_style']}."
    )


def _read_generate_image_result(result_text: str) -> dict[str, str]:
    result = json.loads(result_text)
    if not isinstance(result, dict):
        raise ValueError("generate_image returned an unexpected result.")

    image_base64 = result.get("image_base64")
    if not isinstance(image_base64, str) or not image_base64:
        raise ValueError("generate_image returned no image_base64 value.")

    return {
        "image_base64": image_base64,
        "mime_type": _read_optional_string(result, "mime_type"),
        "model": _read_optional_string(result, "model"),
        "size": _read_optional_string(result, "size"),
    }


def _read_optional_string(data: dict[str, object], key: str) -> str:
    value = data.get(key)
    if isinstance(value, str):
        return value

    return ""


def _decode_base64_image(image_base64: str) -> bytes:
    encoded_image = image_base64.strip()
    if encoded_image.lower().startswith("data:") and "," in encoded_image:
        _prefix, encoded_image = encoded_image.split(",", 1)
    if not encoded_image:
        raise ValueError("Image data must not be empty.")

    try:
        return base64.b64decode(encoded_image, validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("Image data must be valid base64.") from error


def _extract_json_object(text: str) -> str:
    stripped_text = text.strip()
    if stripped_text.startswith("{") and stripped_text.endswith("}"):
        return stripped_text

    start_index = stripped_text.find("{")
    end_index = stripped_text.rfind("}")
    if start_index == -1 or end_index == -1 or end_index < start_index:
        raise ValueError("Poster Agent did not receive a JSON object.")

    return stripped_text[start_index : end_index + 1]
