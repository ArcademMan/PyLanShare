"""Receiver: WebSocket server that receives and writes files."""

import asyncio
import logging
import os
import shutil
import stat
import zlib
from pathlib import Path

import websockets

from ..core.protocol import PROTOCOL_VERSION, MsgType, make_msg, parse_chunk_frame, parse_msg
from ..core.transfer import build_manifest, hash_file

log = logging.getLogger("pylanshare.receiver")


class Receiver:
    def __init__(self, dest_dir: Path, host: str = "0.0.0.0", port: int = 8765, *,
                 token: str | None = None, ignore_patterns: list[str] | None = None,
                 max_connections: int = 3, ssl_context=None):
        self.dest_dir = dest_dir.resolve()
        self.host = host
        self.port = port
        self._token = token
        self._ignore_patterns = ignore_patterns
        self._max_connections = max_connections
        self._ssl_context = ssl_context
        self._running = False
        self._server = None
        self._active_connections: set = set()
        # Callbacks for GUI
        self.on_log: list = []
        self.on_status: list = []
        self.on_progress: list = []
        self.on_connected: list = []

    def _emit_log(self, msg: str):
        log.info(msg)
        for cb in self.on_log:
            cb(msg)

    def _emit_status(self, msg: str):
        for cb in self.on_status:
            cb(msg)

    def _emit_progress(self, filename: str, received: int, total: int):
        for cb in self.on_progress:
            cb(filename, received, total)

    def _emit_connected(self, connected: bool):
        for cb in self.on_connected:
            cb(connected)

    @staticmethod
    def _force_writable(path: Path):
        """Remove read-only flag on Windows."""
        try:
            os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
        except OSError:
            pass

    def _safe_delete(self, path: Path):
        """Delete a file, handling read-only on Windows."""
        try:
            self._force_writable(path)
            if path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
            else:
                path.unlink()
        except OSError as e:
            self._emit_log(f"Warning: could not delete {path}: {e}")

    def _safe_replace(self, src: Path, dest: Path):
        """Replace dest with src, handling read-only on Windows."""
        try:
            if dest.exists():
                self._force_writable(dest)
                dest.unlink()
            src.rename(dest)
        except OSError:
            # Fallback: copy + delete
            try:
                shutil.copy2(src, dest)
                src.unlink()
            except OSError as e:
                self._emit_log(f"Warning: could not replace {dest}: {e}")

    def _cleanup_empty_parents(self, parent: Path):
        """Remove empty parent directories up to dest_dir."""
        try:
            while parent != self.dest_dir:
                parent.rmdir()
                parent = parent.parent
        except OSError:
            pass

    async def _handle_connection(self, ws):
        if self._max_connections > 0 and len(self._active_connections) >= self._max_connections:
            self._emit_log(f"Rejected connection from {ws.remote_address}: max connections reached")
            await ws.send(make_msg(MsgType.ERROR, error="Server at max connections"))
            await ws.close()
            return
        self._active_connections.add(ws)
        self._emit_log(f"Sender connected from {ws.remote_address}")
        self._emit_status("Connected")
        self._emit_connected(True)

        current_file: dict | None = None
        tmp_handle = None
        bytes_received = 0

        try:
            async for raw in ws:
                if isinstance(raw, bytes):
                    if current_file is None:
                        self._emit_log("Warning: received chunk without FILE_START")
                        continue
                    compressed = parse_chunk_frame(raw)
                    data = zlib.decompress(compressed)
                    tmp_handle.write(data)
                    bytes_received += len(data)
                    self._emit_progress(
                        current_file["path"], bytes_received, current_file["size"]
                    )
                    continue

                msg = parse_msg(raw)
                mt = msg["type"]

                if mt == MsgType.HANDSHAKE:
                    version = msg.get("version", 0)
                    if version != PROTOCOL_VERSION:
                        self._emit_log(f"Protocol mismatch: {version} != {PROTOCOL_VERSION}")
                        await ws.send(make_msg(MsgType.ERROR, error="Protocol version mismatch"))
                        return
                    # Token validation — both sides must match
                    received_token = msg.get("token", "")
                    local_token = self._token or ""
                    if received_token != local_token:
                        self._emit_log(f"Authentication failed from {ws.remote_address}")
                        await ws.send(make_msg(MsgType.ERROR, error="Authentication failed: password mismatch"))
                        return
                    await ws.send(make_msg(MsgType.HANDSHAKE_ACK, version=PROTOCOL_VERSION))
                    self._emit_log("Handshake OK")

                elif mt == MsgType.MANIFEST:
                    sender_files = msg["files"]
                    local_manifest = build_manifest(self.dest_dir,
                                                     ignore_patterns=self._ignore_patterns)

                    needed = []
                    for path, info in sender_files.items():
                        local = local_manifest.get(path)
                        if local is None or local["hash"] != info["hash"]:
                            needed.append(path)

                    deleted = [p for p in local_manifest if p not in sender_files]

                    self._emit_log(f"Manifest diff: need {len(needed)}, delete {len(deleted)}")
                    await ws.send(make_msg(
                        MsgType.MANIFEST_DIFF, needed=needed, deleted=deleted
                    ))

                elif mt == MsgType.FILE_START:
                    rel_path = msg["path"]
                    dest = self.dest_dir / rel_path
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    tmp_path = dest.with_name(dest.name + ".pylanshare.tmp")
                    tmp_handle = open(tmp_path, "wb")
                    bytes_received = 0
                    current_file = msg
                    self._emit_log(f"Receiving: {rel_path} ({msg['size']:,} bytes)")
                    self._emit_status(f"Receiving {rel_path}")

                elif mt == MsgType.FILE_END:
                    if tmp_handle:
                        tmp_handle.close()
                        tmp_handle = None
                    rel_path = msg["path"]
                    dest = self.dest_dir / rel_path
                    tmp_path = dest.with_name(dest.name + ".pylanshare.tmp")

                    # Hash verification
                    expected_hash = current_file.get("hash") if current_file else None
                    if expected_hash:
                        actual_hash = hash_file(tmp_path)
                        if actual_hash != expected_hash:
                            self._emit_log(
                                f"Hash mismatch for {rel_path}: "
                                f"expected {expected_hash[:12]}… got {actual_hash[:12]}…"
                            )
                            try:
                                tmp_path.unlink()
                            except OSError:
                                pass
                            current_file = None
                            self._emit_status("Waiting")
                            continue

                    self._safe_replace(tmp_path, dest)

                    # Preserve original modification time
                    mtime = current_file.get("mtime") if current_file else None
                    if mtime is not None:
                        try:
                            os.utime(dest, (mtime, mtime))
                        except OSError:
                            pass

                    self._emit_log(f"Received: {rel_path}")
                    current_file = None
                    self._emit_status("Waiting")

                elif mt == MsgType.FILE_DELETE:
                    rel_path = msg["path"]
                    dest = self.dest_dir / rel_path
                    if dest.exists():
                        self._safe_delete(dest)
                        self._emit_log(f"Deleted: {rel_path}")
                        self._cleanup_empty_parents(dest.parent)

                elif mt == MsgType.PING:
                    await ws.send(make_msg(MsgType.PONG))

                elif mt == MsgType.SYNC_COMPLETE:
                    self._emit_log("Full sync complete")
                    self._emit_status("Waiting for changes")

        except websockets.ConnectionClosed:
            self._emit_log("Sender disconnected")
        finally:
            if tmp_handle:
                tmp_handle.close()
            self._active_connections.discard(ws)
            self._emit_connected(False)
            self._emit_log("Waiting for reconnection...")
            self._emit_status("Waiting for connection")

    def _cleanup_orphaned_temps(self):
        """Remove leftover .pylanshare.tmp files from interrupted transfers."""
        count = 0
        for tmp in self.dest_dir.rglob("*.pylanshare.tmp"):
            try:
                tmp.unlink()
                count += 1
            except OSError:
                pass
        if count:
            self._emit_log(f"Cleaned up {count} orphaned temp file(s)")

    async def run(self):
        self._running = True
        self.dest_dir.mkdir(parents=True, exist_ok=True)
        self._cleanup_orphaned_temps()
        self._emit_log(f"Listening on {self.host}:{self.port}")
        self._emit_log(f"Destination: {self.dest_dir}")
        self._emit_status("Waiting for connection")

        scheme = "wss" if self._ssl_context else "ws"
        self._server = await websockets.serve(
            self._handle_connection,
            self.host,
            self.port,
            max_size=None,
            ssl=self._ssl_context,
        )
        self._emit_log(f"Protocol: {scheme}")
        try:
            while self._running:
                await asyncio.sleep(1)
        finally:
            self._server.close()
            await self._server.wait_closed()

    def stop(self):
        self._running = False
        # Close all active connections
        for ws in list(self._active_connections):
            ws.close()
        self._active_connections.clear()
        if self._server:
            self._server.close()
