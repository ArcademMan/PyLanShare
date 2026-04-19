"""File hashing, chunking, and compression utilities."""

import asyncio
import hashlib
import os
import zlib
from pathlib import Path
from typing import AsyncGenerator, Generator

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


async def aread_chunks(filepath: Path, compression_level: int = 6) -> AsyncGenerator[bytes, None]:
    """Yield compressed chunks without blocking the event loop.

    File I/O and compression run in a thread so the event loop stays responsive.
    """
    def _read_and_compress(fpath, level):
        chunks = []
        with open(fpath, "rb") as f:
            while True:
                block = f.read(CHUNK_SIZE)
                if not block:
                    break
                chunks.append(zlib.compress(block, level=level))
        return chunks

    # For files <= 16 MB, do it all in one thread call to reduce overhead
    file_size = filepath.stat().st_size
    if file_size <= 16 * 1024 * 1024:
        chunks = await asyncio.to_thread(_read_and_compress, filepath, compression_level)
        for chunk in chunks:
            yield chunk
    else:
        # For large files, read+compress one chunk at a time in a thread
        # to avoid loading the whole file into memory
        def _read_one(f, level):
            block = f.read(CHUNK_SIZE)
            if not block:
                return None
            return zlib.compress(block, level=level)

        f = await asyncio.to_thread(open, filepath, "rb")
        try:
            while True:
                compressed = await asyncio.to_thread(_read_one, f, compression_level)
                if compressed is None:
                    break
                yield compressed
        finally:
            await asyncio.to_thread(f.close)


async def aread_chunks_hashed(
    filepath: Path, compression_level: int, hasher
) -> AsyncGenerator[tuple[bytes, int], None]:
    """Yield (compressed_chunk, raw_byte_count) while updating *hasher* incrementally.

    Single-pass: the file is read once, hashed and compressed in the same thread
    call, so callers never need a separate hash_file() read.
    """

    file_size = filepath.stat().st_size
    if file_size <= 16 * 1024 * 1024:
        def _read_all(fpath, level, h):
            results = []
            with open(fpath, "rb") as f:
                while True:
                    block = f.read(CHUNK_SIZE)
                    if not block:
                        break
                    h.update(block)
                    results.append((zlib.compress(block, level=level), len(block)))
            return results

        chunks = await asyncio.to_thread(_read_all, filepath, compression_level, hasher)
        for item in chunks:
            yield item
    else:
        def _read_one(f, level, h):
            block = f.read(CHUNK_SIZE)
            if not block:
                return None
            h.update(block)
            return zlib.compress(block, level=level), len(block)

        f = await asyncio.to_thread(open, filepath, "rb")
        try:
            while True:
                result = await asyncio.to_thread(_read_one, f, compression_level, hasher)
                if result is None:
                    break
                yield result
        finally:
            await asyncio.to_thread(f.close)


def build_manifest(base_dir: Path, ignore_patterns: list[str] | None = None,
                    quick: bool = False) -> dict[str, dict]:
    """Build a manifest of {relative_path: {hash, size, mtime}} for all files.

    If quick=True, skip SHA-256 hashing (use mtime+size only). Much faster
    for large directories — suitable for sync mode where hash verification
    happens per-file during transfer.
    """
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
            try:
                st = filepath.stat()
            except OSError:
                continue
            entry = {"size": st.st_size, "mtime": st.st_mtime}
            if not quick:
                entry["hash"] = hash_file(filepath)
            manifest[rel] = entry
    return manifest
