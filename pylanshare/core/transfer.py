"""File hashing, chunking, and compression utilities."""

import hashlib
import os
import zlib
from pathlib import Path
from typing import Generator

from .ignore import is_ignored
from .protocol import CHUNK_SIZE


def hash_file(filepath: Path) -> str:
    """Compute SHA-256 hash of a file, reading in chunks."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while True:
            block = f.read(CHUNK_SIZE)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def read_chunks(filepath: Path, compression_level: int = 6) -> Generator[bytes, None, None]:
    """Yield compressed chunks of a file."""
    with open(filepath, "rb") as f:
        while True:
            block = f.read(CHUNK_SIZE)
            if not block:
                break
            yield zlib.compress(block, level=compression_level)


def build_manifest(base_dir: Path, ignore_patterns: list[str] | None = None) -> dict[str, dict]:
    """Build a manifest of {relative_path: {hash, size, mtime}} for all files."""
    patterns = ignore_patterns or []
    manifest = {}
    for root, dirs, files in os.walk(base_dir):
        # Prune ignored directories in-place
        if patterns:
            dirs[:] = [d for d in dirs if not is_ignored(d, patterns)]
        for name in files:
            filepath = Path(root) / name
            rel = filepath.relative_to(base_dir).as_posix()
            if patterns and is_ignored(rel, patterns):
                continue
            stat = filepath.stat()
            manifest[rel] = {
                "hash": hash_file(filepath),
                "size": stat.st_size,
                "mtime": stat.st_mtime,
            }
    return manifest
