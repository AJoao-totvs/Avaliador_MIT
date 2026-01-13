"""
Knowledge base loader for evaluation criteria and prompts.

Loads JSON criteria files and text prompts for MIT evaluation.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

# Base directory for knowledge base files
KB_DIR = Path(__file__).parent


@lru_cache(maxsize=10)
def load_criteria(mit_type: str) -> dict[str, Any]:
    """
    Load evaluation criteria for a specific MIT type.

    Args:
        mit_type: Type of MIT (e.g., "MIT041", "MIT043").

    Returns:
        Dictionary with evaluation criteria.

    Raises:
        FileNotFoundError: If criteria file does not exist.
        ValueError: If criteria file is invalid JSON.
    """
    # Normalize MIT type
    mit_type = mit_type.upper().replace("-", "").replace("_", "")
    if not mit_type.startswith("MIT"):
        mit_type = f"MIT{mit_type}"

    # Map to filename
    filename_map = {
        "MIT041": "mit041.json",
        "MIT043": "mit043.json",
        "MIT037": "mit037.json",
        "MIT045": "mit045.json",
        "MIT065": "mit065.json",
    }

    filename = filename_map.get(mit_type)
    if not filename:
        raise ValueError(f"Unknown MIT type: {mit_type}")

    criteria_path = KB_DIR / filename
    if not criteria_path.exists():
        raise FileNotFoundError(f"Criteria file not found for {mit_type}: {criteria_path}")

    try:
        return json.loads(criteria_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in criteria file {criteria_path}: {e}") from e


@lru_cache(maxsize=20)
def get_prompt(prompt_name: str) -> str:
    """
    Load a prompt template from the prompts directory.

    Args:
        prompt_name: Name of the prompt file (without .txt extension).

    Returns:
        Prompt text content.

    Raises:
        FileNotFoundError: If prompt file does not exist.
    """
    prompts_dir = KB_DIR / "prompts"

    # Try with and without .txt extension
    for ext in ["", ".txt"]:
        prompt_path = prompts_dir / f"{prompt_name}{ext}"
        if prompt_path.exists():
            return prompt_path.read_text(encoding="utf-8")

    raise FileNotFoundError(f"Prompt file not found: {prompt_name} (searched in {prompts_dir})")


def get_available_mit_types() -> list[str]:
    """
    Get list of available MIT types with criteria files.

    Returns:
        List of MIT type identifiers.
    """
    available = []
    for json_file in KB_DIR.glob("mit*.json"):
        mit_type = json_file.stem.upper()
        if not mit_type.startswith("MIT"):
            mit_type = f"MIT{mit_type}"
        available.append(mit_type)
    return sorted(available)


def get_available_prompts() -> list[str]:
    """
    Get list of available prompt templates.

    Returns:
        List of prompt names.
    """
    prompts_dir = KB_DIR / "prompts"
    if not prompts_dir.exists():
        return []
    return [p.stem for p in prompts_dir.glob("*.txt")]


def clear_cache() -> None:
    """Clear all cached criteria and prompts."""
    load_criteria.cache_clear()
    get_prompt.cache_clear()
