"""Protocol constants and message helpers for PyLanShare."""

import json
import struct
from enum import Enum

PROTOCOL_VERSION = 2
CHUNK_SIZE = 1024 * 1024  # 1 MB


class MsgType(str, Enum):
    HANDSHAKE = "HANDSHAKE"
    HANDSHAKE_ACK = "HANDSHAKE_ACK"
    FILE_START = "FILE_START"
    FILE_END = "FILE_END"
    FILE_DELETE = "FILE_DELETE"
    MANIFEST = "MANIFEST"
    MANIFEST_DIFF = "MANIFEST_DIFF"
    SYNC_REQUEST = "SYNC_REQUEST"
    SYNC_COMPLETE = "SYNC_COMPLETE"
    PING = "PING"
    PONG = "PONG"
    ERROR = "ERROR"


# Binary chunk header: 4 bytes magic + 4 bytes compressed length
CHUNK_MAGIC = b"PLSC"


def make_msg(msg_type: MsgType, **kwargs) -> str:
    return json.dumps({"type": msg_type.value, **kwargs})


def parse_msg(data: str) -> dict:
    return json.loads(data)


def make_chunk_frame(compressed_data: bytes) -> bytes:
    """Create a binary frame: magic (4B) + length (4B big-endian) + compressed data."""
    return CHUNK_MAGIC + struct.pack(">I", len(compressed_data)) + compressed_data


def parse_chunk_frame(data: bytes) -> bytes:
    """Parse a binary frame, return compressed data."""
    if not data.startswith(CHUNK_MAGIC):
        raise ValueError("Invalid chunk frame: bad magic")
    length = struct.unpack(">I", data[4:8])[0]
    return data[8 : 8 + length]
