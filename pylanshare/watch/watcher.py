"""Filesystem watcher with debounce using watchdog."""

import asyncio
import time
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer


class _DebouncedHandler(FileSystemEventHandler):
    """Collects filesystem events and debounces them."""

    def __init__(self, loop: asyncio.AbstractEventLoop, queue: asyncio.Queue,
                 watch_dir: Path, ignore_patterns: list[str] | None = None,
                 debounce_sec: float = 0.5):
        super().__init__()
        self._loop = loop
        self._queue = queue
        self._watch_dir = watch_dir
        self._ignore_patterns = ignore_patterns or []
        self._debounce_sec = debounce_sec
        self._pending: dict[str, tuple[str, float]] = {}

    def _handle(self, event: FileSystemEvent):
        if event.is_directory:
            return
        src = event.src_path
        if self._ignore_patterns:
            from ..core.ignore import is_ignored
            try:
                rel = Path(src).relative_to(self._watch_dir).as_posix()
            except ValueError:
                return
            if is_ignored(rel, self._ignore_patterns):
                return
        self._pending[src] = (event.event_type, time.monotonic())
        self._loop.call_soon_threadsafe(asyncio.ensure_future, self._flush(src))

    async def _flush(self, path: str):
        await asyncio.sleep(self._debounce_sec)
        entry = self._pending.get(path)
        if entry is None:
            return
        event_type, ts = entry
        if time.monotonic() - ts >= self._debounce_sec - 0.05:
            self._pending.pop(path, None)
            await self._queue.put((event_type, path))

    def on_created(self, event):
        self._handle(event)

    def on_modified(self, event):
        self._handle(event)

    def on_deleted(self, event):
        self._handle(event)

    def _is_src_ignored(self, src: str) -> bool:
        """Check if a source path should be ignored."""
        if not self._ignore_patterns:
            return False
        from ..core.ignore import is_ignored
        try:
            rel = Path(src).relative_to(self._watch_dir).as_posix()
        except ValueError:
            return True
        return is_ignored(rel, self._ignore_patterns)

    def on_moved(self, event):
        if event.is_directory:
            # Directory rename: emit delete for old paths, create for new paths
            src_dir = Path(event.src_path)
            dest_dir = Path(event.dest_path)
            for filepath in dest_dir.rglob("*"):
                if filepath.is_file():
                    # Infer old path from relative position
                    rel = filepath.relative_to(dest_dir)
                    old_path = str(src_dir / rel)
                    if not self._is_src_ignored(old_path):
                        self._pending[old_path] = ("deleted", time.monotonic())
                        self._loop.call_soon_threadsafe(
                            asyncio.ensure_future, self._flush(old_path)
                        )
                    # Emit create for new path
                    self._handle(
                        type("E", (), {
                            "is_directory": False,
                            "src_path": str(filepath),
                            "event_type": "created",
                        })()
                    )
        else:
            # File rename: delete old + create new, with ignore check
            if not self._is_src_ignored(event.src_path):
                self._pending[event.src_path] = ("deleted", time.monotonic())
                self._loop.call_soon_threadsafe(
                    asyncio.ensure_future, self._flush(event.src_path)
                )
            self._handle(
                type("E", (), {
                    "is_directory": False,
                    "src_path": event.dest_path,
                    "event_type": "created",
                })()
            )


class FolderWatcher:
    """Watches a directory and yields (event_type, path) tuples via an async queue."""

    def __init__(self, watch_dir: Path, ignore_patterns: list[str] | None = None,
                 debounce_sec: float = 0.5):
        self.watch_dir = watch_dir
        self._ignore_patterns = ignore_patterns
        self.debounce_sec = debounce_sec
        self.queue: asyncio.Queue = asyncio.Queue()
        self._observer: Observer | None = None

    def start(self, loop: asyncio.AbstractEventLoop):
        handler = _DebouncedHandler(loop, self.queue, self.watch_dir,
                                    self._ignore_patterns, self.debounce_sec)
        self._observer = Observer()
        self._observer.schedule(handler, str(self.watch_dir), recursive=True)
        self._observer.start()

    def stop(self):
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
