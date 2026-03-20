"""Ignore patterns for file sync filtering."""

import fnmatch
from pathlib import Path

from shared.config import get as config_get, set as config_set

DEFAULT_PATTERNS = [
    "__pycache__",
    "*.pyc",
    ".git",
    ".venv",
    ".env",
    "*.tmp",
    ".DS_Store",
    "*.pylanshare.tmp",
    "Thumbs.db",
]


def load_patterns(watch_dir: Path) -> list[str]:
    key = f"ignore_patterns:{watch_dir.resolve()}"
    saved = config_get(key)
    if saved is not None:
        return saved
    return list(DEFAULT_PATTERNS)


def save_patterns(watch_dir: Path, patterns: list[str]):
    key = f"ignore_patterns:{watch_dir.resolve()}"
    config_set(key, patterns)


def is_ignored(rel_path: str, patterns: list[str]) -> bool:
    parts = rel_path.replace("\\", "/").split("/")
    for pattern in patterns:
        # Check each path component (catches directory patterns like __pycache__)
        for part in parts:
            if fnmatch.fnmatch(part, pattern):
                return True
        # Check full path (catches patterns like "build/*.log")
        if fnmatch.fnmatch(rel_path, pattern):
            return True
    return False
