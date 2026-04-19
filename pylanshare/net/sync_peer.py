"""Bidirectional sync peers for multi-device LAN synchronization.

SyncServer listens for connections and relays changes to all peers.
SyncClient connects to a SyncServer and syncs bidirectionally.
"""

import asyncio
import hashlib
import logging
import os
import shutil
import stat
import time
import zlib
from pathlib import Path

import websockets

from ..core.protocol import (
    PROTOCOL_VERSION,
    MsgType,
    make_chunk_frame,
    make_msg,
    parse_chunk_frame,
    parse_msg,
)
from ..core.transfer import aread_chunks_hashed, build_manifest
from ..watch.watcher import FolderWatcher

log = logging.getLogger("pylanshare.sync")

PING_INTERVAL = 15
PING_TIMEOUT = 30
RECONNECT_BASE = 5
RECONNECT_MAX = 60
ECHO_SUPPRESS_SEC = 2.0

# Sentinel pushed to control_queue when peer disconnects
_DISCONNECTED = "_DISCONNECTED"


class _SyncBase:
    """Shared logic for SyncServer and SyncClient."""

    def __init__(self, sync_dir: Path, *, token: str | None = None,
                 ignore_patterns: list[str] | None = None,
                 compression_level: int = 0, rate_limit: int = 0,
                 ssl_context=None):
        self.sync_dir = sync_dir.resolve()
        self._token = token
        self._ignore_patterns = ignore_patterns
        self._compression_level = compression_level
        self._rate_limit = rate_limit
        self._ssl_context = ssl_context
        self._running = False
        self._recently_written: dict[str, float] = {}
        # GUI callbacks
        self.on_log: list = []
        self.on_status: list = []
        self.on_progress: list = []
        self.on_connected: list = []
        self.on_reconnecting: list = []

    # -- Emit helpers --------------------------------------------------

    def _emit_log(self, msg: str):
        log.info(msg)
        for cb in self.on_log:
            cb(msg)

    def _emit_status(self, msg: str):
        for cb in self.on_status:
            cb(msg)

    def _emit_progress(self, filename: str, current: int, total: int):
        for cb in self.on_progress:
            cb(filename, current, total)

    def _emit_connected(self, connected: bool):
        for cb in self.on_connected:
            cb(connected)

    def _emit_reconnecting(self, reconnecting: bool):
        for cb in self.on_reconnecting:
            cb(reconnecting)

    # -- File helpers --------------------------------------------------

    @staticmethod
    def _force_writable(path: Path):
        try:
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        except OSError:
            pass

    def _safe_delete(self, path: Path):
        try:
            self._force_writable(path)
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink()
        except OSError as e:
            self._emit_log(f"Warning: could not delete {path}: {e}")

    def _safe_replace(self, src: Path, dest: Path):
        try:
            if dest.exists():
                self._force_writable(dest)
                dest.unlink()
            src.rename(dest)
        except OSError:
            try:
                shutil.copy2(src, dest)
                src.unlink()
            except OSError as e:
                self._emit_log(f"Warning: could not replace {dest}: {e}")

    def _cleanup_empty_parents(self, parent: Path):
        try:
            while parent != self.sync_dir:
                parent.rmdir()
                parent = parent.parent
        except OSError:
            pass

    def _cleanup_orphaned_temps(self):
        count = 0
        for tmp in self.sync_dir.rglob("*.pylanshare.tmp"):
            try:
                tmp.unlink()
                count += 1
            except OSError:
                pass
        if count:
            self._emit_log(f"Cleaned up {count} orphaned temp file(s)")

    # -- Echo suppression ----------------------------------------------

    def _mark_written(self, rel_path: str):
        self._recently_written[rel_path] = time.monotonic()

    def _is_echo(self, rel_path: str) -> bool:
        ts = self._recently_written.get(rel_path)
        if ts is not None:
            if time.monotonic() - ts < ECHO_SUPPRESS_SEC:
                return True
            del self._recently_written[rel_path]
        return False

    # -- Send a single file --------------------------------------------

    async def _send_file(self, ws, rel_path: str):
        filepath = self.sync_dir / rel_path
        if not filepath.is_file():
            return
        st = filepath.stat()

        self._emit_log(f"Sending: {rel_path} ({st.st_size:,} bytes)")
        self._emit_status(f"Sending {rel_path}")

        await ws.send(make_msg(
            MsgType.FILE_START,
            path=rel_path, size=st.st_size,
            hash="", mtime=st.st_mtime,
        ))

        hasher = hashlib.sha256()
        bytes_sent = 0
        async for compressed_chunk, raw_len in aread_chunks_hashed(
            filepath, self._compression_level, hasher
        ):
            await ws.send(make_chunk_frame(compressed_chunk))
            bytes_sent = min(bytes_sent + raw_len, st.st_size)
            self._emit_progress(rel_path, bytes_sent, st.st_size)
            if self._rate_limit > 0:
                await asyncio.sleep(len(compressed_chunk) / self._rate_limit)
            else:
                await asyncio.sleep(0)

        file_hash = hasher.hexdigest()
        await ws.send(make_msg(MsgType.FILE_END, path=rel_path, hash=file_hash))
        self._emit_log(f"Sent: {rel_path}")

    # -- Push sync: send manifest, wait for diff, send files -----------

    async def _push_sync(self, ws, control_queue: asyncio.Queue):
        self._emit_log("Building file manifest...")
        self._emit_status("Building manifest")
        manifest = await asyncio.to_thread(
            build_manifest, self.sync_dir,
            ignore_patterns=self._ignore_patterns, quick=True,
        )
        self._emit_log(f"Manifest: {len(manifest)} files")

        await ws.send(make_msg(MsgType.MANIFEST, files=manifest))

        response = await control_queue.get()
        if response.get("type") == _DISCONNECTED:
            return
        if response["type"] == MsgType.MANIFEST_DIFF:
            needed = response.get("needed", [])
            self._emit_log(f"Sync: {len(needed)} files to send")
            for rel_path in needed:
                await self._send_file(ws, rel_path)

        await ws.send(make_msg(MsgType.SYNC_COMPLETE))
        self._emit_log("Push sync complete")

    # -- Handle incoming manifest (compute diff with mtime, reply) -----

    async def _handle_incoming_manifest(self, ws, remote_files: dict):
        local_manifest = await asyncio.to_thread(
            build_manifest, self.sync_dir,
            ignore_patterns=self._ignore_patterns, quick=True,
        )
        needed = []
        for path, info in remote_files.items():
            local = local_manifest.get(path)
            if local is None:
                needed.append(path)
            elif local["size"] != info["size"] or abs(local["mtime"] - info["mtime"]) > 0.01:
                # Different size or mtime → request if remote is newer
                if info["mtime"] > local["mtime"]:
                    needed.append(path)
        # No deletions in sync mode initial exchange
        self._emit_log(f"Manifest diff: need {len(needed)} files")
        await ws.send(make_msg(MsgType.MANIFEST_DIFF, needed=needed, deleted=[]))

    # -- Handle incoming file messages ---------------------------------

    def _begin_file_receive(self, msg: dict, recv_state: dict):
        rel_path = msg["path"]
        dest = self.sync_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = dest.with_name(dest.name + ".pylanshare.tmp")
        recv_state["current_file"] = msg
        recv_state["tmp_handle"] = open(tmp_path, "wb")
        recv_state["bytes_received"] = 0
        recv_state["hasher"] = hashlib.sha256()
        self._emit_log(f"Receiving: {rel_path} ({msg['size']:,} bytes)")
        self._emit_status(f"Receiving {rel_path}")

    async def _receive_chunk(self, raw: bytes, recv_state: dict):
        if recv_state["tmp_handle"] is None:
            return

        def _process(raw_data, state):
            compressed = parse_chunk_frame(raw_data)
            data = zlib.decompress(compressed)
            state["tmp_handle"].write(data)
            state["hasher"].update(data)
            state["bytes_received"] += len(data)

        await asyncio.to_thread(_process, raw, recv_state)
        cf = recv_state["current_file"]
        if cf:
            self._emit_progress(cf["path"], recv_state["bytes_received"], cf["size"])
        await asyncio.sleep(0.005)

    def _finish_file_receive(self, msg: dict, recv_state: dict):
        """Finalize a received file. Returns the rel_path on success, None on failure."""
        if recv_state["tmp_handle"]:
            recv_state["tmp_handle"].close()
            recv_state["tmp_handle"] = None

        cf = recv_state["current_file"]
        if cf is None:
            return None

        rel_path = msg["path"]
        dest = self.sync_dir / rel_path
        tmp_path = dest.with_name(dest.name + ".pylanshare.tmp")

        expected_hash = msg.get("hash") or cf.get("hash")
        if expected_hash:
            actual_hash = recv_state["hasher"].hexdigest()
            if actual_hash != expected_hash:
                self._emit_log(
                    f"Hash mismatch for {rel_path}: "
                    f"expected {expected_hash[:12]}... got {actual_hash[:12]}..."
                )
                try:
                    tmp_path.unlink()
                except OSError:
                    pass
                recv_state["current_file"] = None
                return None

        self._safe_replace(tmp_path, dest)

        mtime = cf.get("mtime")
        if mtime is not None:
            try:
                os.utime(dest, (mtime, mtime))
            except OSError:
                pass

        self._mark_written(rel_path)
        self._emit_log(f"Received: {rel_path}")
        recv_state["current_file"] = None
        self._emit_status("Waiting")
        return rel_path

    def _handle_file_delete(self, msg: dict):
        rel_path = msg["path"]
        dest = self.sync_dir / rel_path
        if not dest.exists():
            return
        if dest.is_dir():
            # Safety: never delete directories via FILE_DELETE in sync mode
            # to prevent cascade deletions
            self._emit_log(f"Ignored directory delete: {rel_path}")
            return
        self._safe_delete(dest)
        self._emit_log(f"Deleted: {rel_path}")
        self._mark_written(rel_path)
        # No _cleanup_empty_parents in sync mode: removing empty dirs
        # triggers watcher events that cascade back to the other peer


# ======================================================================
# SyncServer
# ======================================================================

class SyncServer(_SyncBase):
    """WebSocket server that syncs bidirectionally with multiple peers."""

    def __init__(self, sync_dir: Path, host: str = "0.0.0.0", port: int = 8765, *,
                 max_connections: int = 10, **kwargs):
        super().__init__(sync_dir, **kwargs)
        self.host = host
        self.port = port
        self._max_connections = max_connections
        self._peers: set = set()
        self._ready_peers: set = set()
        self._send_locks: dict = {}
        self._server = None
        self._watcher: FolderWatcher | None = None

    # -- Relay helpers -------------------------------------------------

    async def _relay_file_to_others(self, sender_ws, rel_path: str):
        """After receiving a file from one peer, re-send it to all others."""
        for peer in list(self._ready_peers):
            if peer == sender_ws:
                continue
            lock = self._send_locks.get(peer)
            if lock:
                async with lock:
                    try:
                        await self._send_file(peer, rel_path)
                    except websockets.ConnectionClosed:
                        pass

    async def _relay_delete_to_others(self, sender_ws, rel_path: str):
        """After deleting a file, notify all other ready peers."""
        delete_msg = make_msg(MsgType.FILE_DELETE, path=rel_path)
        for peer in list(self._ready_peers):
            if peer == sender_ws:
                continue
            try:
                await peer.send(delete_msg)
            except websockets.ConnectionClosed:
                pass

    # -- Per-connection receive loop -----------------------------------

    async def _connection_receive_loop(self, ws, recv_state: dict,
                                       control_queue: asyncio.Queue):
        try:
            async for raw in ws:
                if isinstance(raw, bytes):
                    await self._receive_chunk(raw, recv_state)
                    continue

                msg = parse_msg(raw)
                mt = msg["type"]

                if mt == MsgType.MANIFEST:
                    await self._handle_incoming_manifest(ws, msg["files"])

                elif mt == MsgType.MANIFEST_DIFF:
                    await control_queue.put(msg)

                elif mt == MsgType.SYNC_COMPLETE:
                    await control_queue.put(msg)

                elif mt == MsgType.FILE_START:
                    self._begin_file_receive(msg, recv_state)

                elif mt == MsgType.FILE_END:
                    rel_path = self._finish_file_receive(msg, recv_state)
                    if rel_path:
                        asyncio.ensure_future(
                            self._relay_file_to_others(ws, rel_path)
                        )

                elif mt == MsgType.FILE_DELETE:
                    self._handle_file_delete(msg)
                    asyncio.ensure_future(
                        self._relay_delete_to_others(ws, msg["path"])
                    )

                elif mt == MsgType.PING:
                    await ws.send(make_msg(MsgType.PONG))

                elif mt == MsgType.SYNC_REQUEST:
                    await control_queue.put(msg)

        except websockets.ConnectionClosed:
            self._emit_log(f"Peer {ws.remote_address} disconnected")
        finally:
            if recv_state["tmp_handle"]:
                recv_state["tmp_handle"].close()
                recv_state["tmp_handle"] = None
            await control_queue.put({"type": _DISCONNECTED})

    # -- Connection handler --------------------------------------------

    async def _handle_connection(self, ws):
        if self._max_connections > 0 and len(self._peers) >= self._max_connections:
            self._emit_log(f"Rejected {ws.remote_address}: max connections")
            await ws.send(make_msg(MsgType.ERROR, error="Server at max connections"))
            await ws.close()
            return

        # -- Handshake --
        try:
            raw = await asyncio.wait_for(ws.recv(), timeout=10)
        except (asyncio.TimeoutError, websockets.ConnectionClosed):
            return

        msg = parse_msg(raw)
        if msg.get("type") != MsgType.HANDSHAKE:
            await ws.send(make_msg(MsgType.ERROR, error="Expected HANDSHAKE"))
            return
        if msg.get("version", 0) != PROTOCOL_VERSION:
            await ws.send(make_msg(MsgType.ERROR, error="Protocol version mismatch"))
            return
        if (msg.get("token", "") or "") != (self._token or ""):
            self._emit_log(f"Auth failed from {ws.remote_address}")
            await ws.send(make_msg(MsgType.ERROR, error="Authentication failed"))
            return

        await ws.send(make_msg(MsgType.HANDSHAKE_ACK, version=PROTOCOL_VERSION,
                                mode="sync"))
        self._emit_log(f"Peer connected from {ws.remote_address}")

        self._peers.add(ws)
        self._send_locks[ws] = asyncio.Lock()
        recv_state = {"current_file": None, "tmp_handle": None, "bytes_received": 0}
        control_queue: asyncio.Queue = asyncio.Queue()
        self._emit_connected(True)

        recv_task = asyncio.ensure_future(
            self._connection_receive_loop(ws, recv_state, control_queue)
        )

        try:
            # Phase 1: wait for client's initial push to complete
            msg = await control_queue.get()
            if msg.get("type") == _DISCONNECTED:
                return
            if msg["type"] == MsgType.SYNC_COMPLETE:
                self._emit_log(f"Received initial sync from {ws.remote_address}")

            # Phase 2: push our files to the client
            lock = self._send_locks[ws]
            async with lock:
                await self._push_sync(ws, control_queue)

            # Mark ready for watcher events
            self._ready_peers.add(ws)
            self._emit_status(f"Syncing ({len(self._ready_peers)} peers)")

            # Phase 3: keep running until disconnect
            await recv_task

        except (websockets.ConnectionClosed, asyncio.CancelledError):
            pass
        finally:
            recv_task.cancel()
            self._peers.discard(ws)
            self._ready_peers.discard(ws)
            self._send_locks.pop(ws, None)
            self._emit_log(f"Peer {ws.remote_address} removed")
            if not self._peers:
                self._emit_connected(False)
            self._emit_status(
                f"Syncing ({len(self._ready_peers)} peers)" if self._ready_peers
                else "Waiting for connections"
            )

    # -- Watcher -------------------------------------------------------

    async def _watch_and_push_all(self):
        """Watch local directory and push changes to all ready peers."""
        while self._running:
            try:
                event_type, abs_path = await asyncio.wait_for(
                    self._watcher.queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue

            abs_p = Path(abs_path)
            # Skip directory events that slipped through watchdog
            if abs_p.exists() and abs_p.is_dir():
                continue

            rel_path = abs_p.relative_to(self.sync_dir).as_posix()
            if self._is_echo(rel_path):
                continue
            if not self._ready_peers:
                continue

            if event_type == "deleted":
                delete_msg = make_msg(MsgType.FILE_DELETE, path=rel_path)
                for peer in list(self._ready_peers):
                    try:
                        await peer.send(delete_msg)
                    except websockets.ConnectionClosed:
                        pass
                self._emit_log(f"Delete: {rel_path}")
            else:
                for peer in list(self._ready_peers):
                    lock = self._send_locks.get(peer)
                    if lock:
                        async with lock:
                            try:
                                await self._send_file(peer, rel_path)
                            except websockets.ConnectionClosed:
                                pass

    # -- Force sync ----------------------------------------------------

    async def force_sync(self):
        """Ask all peers to re-push their manifests."""
        for peer in list(self._ready_peers):
            try:
                await peer.send(make_msg(MsgType.SYNC_REQUEST))
            except websockets.ConnectionClosed:
                pass

    # -- Lifecycle -----------------------------------------------------

    async def run(self):
        self._running = True
        self.sync_dir.mkdir(parents=True, exist_ok=True)
        self._cleanup_orphaned_temps()
        self._emit_log(f"Sync server listening on {self.host}:{self.port}")
        self._emit_log(f"Directory: {self.sync_dir}")
        self._emit_status("Waiting for connections")

        scheme = "wss" if self._ssl_context else "ws"
        self._server = await websockets.serve(
            self._handle_connection,
            self.host, self.port,
            max_size=None, ssl=self._ssl_context,
            max_queue=4, write_limit=2 * 1024 * 1024,
        )
        self._emit_log(f"Protocol: {scheme}")

        loop = asyncio.get_event_loop()
        self._watcher = FolderWatcher(self.sync_dir,
                                       ignore_patterns=self._ignore_patterns)
        self._watcher.start(loop)

        try:
            await self._watch_and_push_all()
        finally:
            self._watcher.stop()
            self._server.close()
            await self._server.wait_closed()

    def stop(self):
        self._running = False
        for ws in list(self._peers):
            ws.close()
        self._peers.clear()
        self._ready_peers.clear()
        if self._watcher:
            self._watcher.stop()
        if self._server:
            self._server.close()


# ======================================================================
# SyncClient
# ======================================================================

class SyncClient(_SyncBase):
    """Connects to a SyncServer and syncs bidirectionally."""

    def __init__(self, sync_dir: Path, host: str, port: int, **kwargs):
        super().__init__(sync_dir, **kwargs)
        self.host = host
        self.port = port
        self._ws = None
        self._watcher: FolderWatcher | None = None
        self._stop_requested = False
        self._last_pong: float = 0
        self._control_queue: asyncio.Queue = asyncio.Queue()

    # -- Receive loop --------------------------------------------------

    async def _receive_loop(self, recv_state: dict,
                            control_queue: asyncio.Queue):
        while self._running:
            try:
                raw = await asyncio.wait_for(self._ws.recv(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except websockets.ConnectionClosed:
                self._emit_log("Connection closed by server")
                self._emit_connected(False)
                self._running = False
                return

            if isinstance(raw, bytes):
                await self._receive_chunk(raw, recv_state)
                continue

            msg = parse_msg(raw)
            mt = msg["type"]

            if mt == MsgType.MANIFEST:
                await self._handle_incoming_manifest(self._ws, msg["files"])

            elif mt == MsgType.MANIFEST_DIFF:
                await control_queue.put(msg)

            elif mt == MsgType.SYNC_COMPLETE:
                await control_queue.put(msg)

            elif mt == MsgType.FILE_START:
                self._begin_file_receive(msg, recv_state)

            elif mt == MsgType.FILE_END:
                self._finish_file_receive(msg, recv_state)

            elif mt == MsgType.FILE_DELETE:
                self._handle_file_delete(msg)

            elif mt == MsgType.PING:
                await self._ws.send(make_msg(MsgType.PONG))

            elif mt == MsgType.PONG:
                self._last_pong = time.monotonic()

            elif mt == MsgType.SYNC_REQUEST:
                self._emit_log("Server requested full sync")
                await self._push_sync(self._ws, control_queue)

    # -- Watch and push ------------------------------------------------

    async def _watch_and_push(self):
        while self._running:
            try:
                event_type, abs_path = await asyncio.wait_for(
                    self._watcher.queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue

            abs_p = Path(abs_path)
            # Skip directory events that slipped through watchdog
            if abs_p.exists() and abs_p.is_dir():
                continue

            rel_path = abs_p.relative_to(self.sync_dir).as_posix()
            if self._is_echo(rel_path):
                continue

            if event_type == "deleted":
                await self._ws.send(make_msg(MsgType.FILE_DELETE, path=rel_path))
                self._emit_log(f"Delete: {rel_path}")
            else:
                await self._send_file(self._ws, rel_path)

    # -- Ping loop -----------------------------------------------------

    async def _ping_loop(self):
        while self._running:
            await asyncio.sleep(PING_INTERVAL)
            if not self._running or not self._ws:
                return
            try:
                await self._ws.send(make_msg(MsgType.PING))
            except websockets.ConnectionClosed:
                self._emit_connected(False)
                self._running = False
                return
            if time.monotonic() - self._last_pong > PING_TIMEOUT:
                self._emit_log("Connection lost (ping timeout)")
                self._emit_connected(False)
                self._running = False
                return

    # -- Force sync ----------------------------------------------------

    async def force_sync(self):
        if self._ws:
            await self._push_sync(self._ws, self._control_queue)

    # -- Session -------------------------------------------------------

    async def _run_session(self) -> bool:
        self._running = True
        scheme = "wss" if self._ssl_context else "ws"
        uri = f"{scheme}://{self.host}:{self.port}"
        self._emit_log(f"Connecting to {uri}...")
        self._emit_status("Connecting")

        async with websockets.connect(uri, max_size=None,
                                       ssl=self._ssl_context,
                                       max_queue=4,
                                       write_limit=2 * 1024 * 1024) as ws:
            self._ws = ws

            # Handshake
            await ws.send(make_msg(
                MsgType.HANDSHAKE,
                version=PROTOCOL_VERSION,
                token=self._token or "",
                mode="sync",
            ))
            ack = parse_msg(await ws.recv())
            if ack["type"] == MsgType.ERROR:
                self._emit_log(f"Rejected: {ack.get('error', 'unknown')}")
                self._emit_connected(False)
                self._stop_requested = True
                return False
            if ack["type"] != MsgType.HANDSHAKE_ACK:
                self._emit_log(f"Handshake failed: {ack}")
                return False

            self._emit_log("Connected!")
            self._emit_connected(True)
            self._emit_reconnecting(False)
            self._last_pong = time.monotonic()

            recv_state = {"current_file": None, "tmp_handle": None,
                          "bytes_received": 0}
            control_queue: asyncio.Queue = asyncio.Queue()
            self._control_queue = control_queue

            recv_task = asyncio.ensure_future(
                self._receive_loop(recv_state, control_queue)
            )

            # Phase 1: push our files to server
            await self._push_sync(ws, control_queue)

            # Phase 2: wait for server's push to complete
            self._emit_status("Receiving sync from server...")
            msg = await control_queue.get()
            if msg["type"] == MsgType.SYNC_COMPLETE:
                self._emit_log("Received sync from server")

            # Phase 3: watch mode
            self._emit_status("Watching for changes")
            loop = asyncio.get_event_loop()
            self._watcher = FolderWatcher(self.sync_dir,
                                           ignore_patterns=self._ignore_patterns)
            self._watcher.start(loop)

            try:
                await asyncio.gather(
                    self._watch_and_push(),
                    recv_task,
                    self._ping_loop(),
                )
            finally:
                self._watcher.stop()
                recv_task.cancel()

        return False

    # -- Main entry with auto-reconnect --------------------------------

    async def run(self):
        self._stop_requested = False
        self.sync_dir.mkdir(parents=True, exist_ok=True)
        self._cleanup_orphaned_temps()
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
