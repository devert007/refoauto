"""Shared utility functions."""

import json
from pathlib import Path


def load_json(filepath: Path) -> list | dict:
    """Load JSON file."""
    if not filepath.exists():
        print(f"Warning: {filepath} not found")
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(filepath: Path, data: list | dict) -> None:
    """Save JSON file with pretty formatting."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Saved: {filepath}")
