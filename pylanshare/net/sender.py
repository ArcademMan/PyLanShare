"""Sender: connects to a receiver via WebSocket and sends files."""

import asyncio
import hashlib
import logging
import time
from pathlib import Path

import websockets

from ..core.protocol import PROTOCOL_VERSION, MsgType, make_chunk_frame, make_msg, parse_msg
from ..core.transfer import aread_chunks_hashed, build_manifest
from ..watch.watcher import FolderWatcher

log = logging.getLogger("pylanshare.sender")

PING_INTERVAL = 15
PING_TIMEOUT = 30
RECONNECT_BASE = 5
RECONNECT_MAX = 60


class Sender:
    def __init__(self, watch_dir: Path, host: str, port: int, *,
                 watch: bool = True, token: str | None = None,
                 ignore_patterns: list[str] | None = None,
                 compression_level: int = 6, rate_limit: int = 0,
                 ssl_context=None):
        self.watch_dir = watch_dir.resolve()
        self.host = host
        self.port = port
        self.watch_enabled = watch
        self._token = token
        self._ignore_patterns = ignore_patterns
        self._compression_level = compression_level
        self._rate_limit = rate_limit
        self._ssl_context = ssl_context
        self._ws = None
        self._watcher: FolderWatcher | None = None
        self._running = False
        self._stop_requested = False
        self._last_pong: float = 0
        self._recv_queue: asyncio.Queue = asyncio.Queue()
        # Callbacks for GUI
        self.on_log: list = []
        self.on_status: list = []
        self.on_progress: list = []
        self.on_connected: list = []
        self.on_reconnecting: list = []

    def _emit_log(self, msg: str):
        log.info(msg)
        for cb in self.on_log:
            cb(msg)

    def _emit_status(self, msg: str):
        for cb in self.on_status:
            cb(msg)

    def _emit_progress(self, filename: str, sent: int, total: int):
        for cb in self.on_progress:
            cb(filename, sent, total)

    def _emit_connected(self, connected: bool):
        for cb in self.on_connected:
            cb(connected)

    def _emit_reconnecting(self, reconnecting: bool):
        for cb in self.on_reconnecting:
            cb(reconnecting)

    async def _send_file(self, rel_path: str):
        filepath = self.watch_dir / rel_path
        if not filepath.is_file():
            return
        st = filepath.stat()

        self._emit_log(f"Sending: {rel_path} ({st.st_size:,} bytes)")
        self._emit_status(f"Sending {rel_path}")

        # Send FILE_START without hash — hash is computed incrementally
        # during the transfer and sent in FILE_END.
        await self._ws.send(make_msg(
            MsgType.FILE_START,
            path=rel_path,
            size=st.st_size,
            hash="",
            mtime=st.st_mtime,
        ))

        hasher = hashlib.sha256()
        bytes_sent = 0
        async for compressed_chunk, raw_len in aread_chunks_hashed(
            filepath, self._compression_level, hasher
        ):
            await self._ws.send(make_chunk_frame(compressed_chunk))
            bytes_sent = min(bytes_sent + raw_len, st.st_size)
            self._emit_progress(rel_path, bytes_sent, st.st_size)
            if self._rate_limit > 0:
                await asyncio.sleep(len(compressed_chunk) / self._rate_limit)
            else:
                await asyncio.sleep(0)

        file_hash = hasher.hexdigest()
        await self._ws.send(make_msg(MsgType.FILE_END, path=rel_path, hash=file_hash))
        self._emit_log(f"Sent: {rel_path}")

    async def _full_sync(self):
        self._emit_log("Building file manifest...")
        self._emit_status("Building manifest")
        manifest = await asyncio.to_thread(
            build_manifest, self.watch_dir,
            ignore_patterns=self._ignore_patterns, quick=True,
        )
        self._emit_log(f"Manifest: {len(manifest)} files")

        await self._ws.send(make_msg(MsgType.MANIFEST, files=manifest))

        response = await self._recv_queue.get()
        if response["type"] == MsgType.MANIFEST_DIFF:
            needed = response.get("needed", [])
            deleted = response.get("deleted", [])
            self._emit_log(f"Sync needed: {len(needed)} to send, {len(deleted)} to delete")

            for rel_path in needed:
                await self._send_file(rel_path)

            for rel_path in deleted:
                await self._ws.send(make_msg(MsgType.FILE_DELETE, path=rel_path))
                self._emit_log(f"Delete: {rel_path}")

        await self._ws.send(make_msg(MsgType.SYNC_COMPLETE))
        self._emit_log("Full sync complete")
        self._emit_status("Watching for changes" if self.watch_enabled else "Idle")

    async def _handle_watch_events(self):
        while self._running:
            try:
                event_type, abs_path = await asyncio.wait_for(
                    self._watcher.queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue

            rel_path = Path(abs_path).relative_to(self.watch_dir).as_posix()

            if event_type == "deleted":
                await self._ws.send(make_msg(MsgType.FILE_DELETE, path=rel_path))
                self._emit_log(f"Delete: {rel_path}")
            else:
                await self._send_file(rel_path)

    async def _recv_loop(self):
        while self._running:
            try:
                raw = await asyncio.wait_for(self._ws.recv(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except websockets.ConnectionClosed:
                self._emit_log("Connection closed by receiver")
                self._emit_connected(False)
                self._running = False
                return

            msg = parse_msg(raw)
            mt = msg["type"]

            if mt == MsgType.PONG:
                self._last_pong = time.monotonic()
            elif mt == MsgType.SYNC_REQUEST:
                self._emit_log("Receiver requested full sync")
                await self._full_sync()
            else:
                await self._recv_queue.put(msg)

    async def _ping_loop(self):
        while self._running:
            await asyncio.sleep(PING_INTERVAL)
            if not self._running or not self._ws:
                return
            try:
                await self._ws.send(make_msg(MsgType.PING))
            except websockets.ConnectionClosed:
                self._emit_log("Connection lost (send ping failed)")
                self._emit_connected(False)
                self._running = False
                return

            if time.monotonic() - self._last_pong > PING_TIMEOUT:
                self._emit_log("Connection lost (ping timeout)")
                self._emit_connected(False)
                self._running = False
                return

    async def force_sync(self):
        if self._ws:
            await self._full_sync()

    async def _run_session(self) -> bool:
        """Run a single connection session. Returns True if clean exit, False if error."""
        self._running = True
        scheme = "wss" if self._ssl_context else "ws"
        uri = f"{scheme}://{self.host}:{self.port}"
        self._emit_log(f"Connecting to {uri}...")
        self._emit_status("Connecting")

        async with websockets.connect(uri, max_size=None, ssl=self._ssl_context,
                                       max_queue=4, write_limit=2 * 1024 * 1024) as ws:
            self._ws = ws

            await ws.send(make_msg(MsgType.HANDSHAKE,
                                   version=PROTOCOL_VERSION,
                                   token=self._token or ""))
            ack = parse_msg(await ws.recv())
            if ack["type"] == MsgType.ERROR:
                self._emit_log(f"Connection rejected: {ack.get('error', 'unknown')}")
                self._emit_connected(False)
                self._stop_requested = True  # Don't retry on auth failure
                return False
            if ack["type"] != MsgType.HANDSHAKE_ACK:
                self._emit_log(f"Handshake failed: {ack}")
                return False

            self._emit_log("Connected!")
            self._emit_status("Connected")
            self._emit_connected(True)
            self._emit_reconnecting(False)
            self._last_pong = time.monotonic()
            self._recv_queue = asyncio.Queue()

            recv_task = asyncio.ensure_future(self._recv_loop())

            await self._full_sync()

            if self.watch_enabled:
                loop = asyncio.get_event_loop()
                self._watcher = FolderWatcher(self.watch_dir,
                                              ignore_patterns=self._ignore_patterns)
                self._watcher.start(loop)
                self._emit_status("Watching for changes")

                try:
                    await asyncio.gather(
                        self._handle_watch_events(),
                        recv_task,
                        self._ping_loop(),
                    )
                finally:
                    self._watcher.stop()
                    recv_task.cancel()
            else:
                recv_task.cancel()
                self._emit_status("Sync complete (no watch mode)")
                return True

        return False

    async def run(self):
        """Main entry point with auto-reconnect."""
        self._stop_requested = False
        delay = RECONNECT_BASE

        while not self._stop_requested:
            try:
                clean = await self._run_session()
                if clean or self._stop_requested:
                    break
            except (OSError, websockets.WebSocketException) as e:
                self._emit_log(f"Connection error: {e}")
                self._emit_connected(False)

            if self._stop_requested:
                break

            # Reconnect with backoff
            self._emit_reconnecting(True)
            self._emit_log(f"Reconnecting in {delay}s...")
            self._emit_status(f"Reconnecting in {delay}s...")

            for _ in range(int(delay * 10)):
                if self._stop_requested:
                    break
                await asyncio.sleep(0.1)

            if self._stop_requested:
                break

            delay = min(delay * 2, RECONNECT_MAX)

        self._ws = None
        self._running = False
        self._emit_status("Stopped")

    def stop(self):
        self._stop_requested = True
        self._running = False
        if self._watcher:
            self._watcher.stop()
