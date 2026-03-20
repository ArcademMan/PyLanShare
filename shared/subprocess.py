"""Wrapper subprocess che nasconde la finestra console su Windows."""

import subprocess
import sys

# Flag per nascondere la console su Windows
_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def run(cmd, **kwargs):
    """subprocess.run() che non mostra la finestra console."""
    kwargs.setdefault("capture_output", True)
    kwargs.setdefault("text", True)
    kwargs.setdefault("encoding", "cp850")
    if sys.platform == "win32":
        kwargs.setdefault("creationflags", _CREATE_NO_WINDOW)
    return subprocess.run(cmd, **kwargs)
