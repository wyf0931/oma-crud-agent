"""Helpers for parsing structured responses from LLMs."""

import json
from typing import Any


def parse_json_response(content: str | None) -> Any:
    """Parse JSON while tolerating fences and short explanatory prefixes."""
    if not content or not content.strip():
        raise ValueError("LLM returned empty content")

    text = content.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        text = text[first_newline + 1 :] if first_newline >= 0 else text[3:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3].rstrip()

    starts = [index for index in (text.find("{"), text.find("[")) if index >= 0]
    if not starts:
        raise ValueError("LLM response does not contain a JSON object or array")

    try:
        value, _ = json.JSONDecoder().raw_decode(text[min(starts) :])
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON response: {exc}") from exc
    return value
