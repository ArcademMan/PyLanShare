"""Async worker thread for running sender/receiver in the background."""

import asyncio

from PySide6.QtCore import QThread, Signal


class AsyncWorker(QThread):
    """Runs an asyncio event loop in a background QThread."""

    log_signal = Signal(str)
    status_signal = Signal(str)
    progress_signal = Signal(str, int, int)
    connected_signal = Signal(bool)
    reconnecting_signal = Signal(bool)
    finished_signal = Signal()

    def __init__(self, coro_factory):
        super().__init__()
        self._coro_factory = coro_factory
        self._loop: asyncio.AbstractEventLoop | None = None
        self._service = None

    def run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._coro_factory(self))
        except Exception as e:
            self.log_signal.emit(f"Error: {e}")
        finally:
            self._loop.close()
            self._loop = None
            self.finished_signal.emit()

    def stop_service(self):
        if self._service:
            self._service.stop()
