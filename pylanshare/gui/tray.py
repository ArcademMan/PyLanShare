"""System tray integration for PyLanShare."""

from PySide6.QtCore import QSize
from PySide6.QtGui import QAction, QColor, QIcon, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from shared.theme import COLORS


def _make_icon(color: str) -> QIcon:
    pixmap = QPixmap(QSize(16, 16))
    pixmap.fill(QColor(color))
    return QIcon(pixmap)


class TrayManager:
    def __init__(self, window):
        self._window = window
        # Create icons lazily (QApplication must exist)
        self._icons = {
            "connected": _make_icon(COLORS["success"]),
            "reconnecting": _make_icon(COLORS["warning"]),
            "disconnected": _make_icon(COLORS["error"]),
            "stopped": _make_icon(COLORS["text_dim"]),
        }
        self._tray = QSystemTrayIcon(window)
        self._tray.setIcon(self._icons["stopped"])
        self._tray.setToolTip("PyLanShare")

        # Context menu
        menu = QMenu()
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {COLORS['bg_light']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['border']};
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 20px;
            }}
            QMenu::item:selected {{
                background-color: {COLORS['primary']};
            }}
            QMenu::separator {{
                height: 1px;
                background: {COLORS['border']};
                margin: 4px 8px;
            }}
        """)

        self._show_action = QAction("Show", window)
        self._show_action.triggered.connect(self._toggle_window)
        menu.addAction(self._show_action)

        sync_action = QAction("Force Sync", window)
        sync_action.triggered.connect(window._on_force_sync)
        menu.addAction(sync_action)

        stop_action = QAction("Stop", window)
        stop_action.triggered.connect(window._on_stop)
        menu.addAction(stop_action)

        menu.addSeparator()

        quit_action = QAction("Quit", window)
        quit_action.triggered.connect(self._quit)
        menu.addAction(quit_action)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)
        self._tray.show()

    def _toggle_window(self):
        if self._window.isVisible():
            self._window.hide()
            self._show_action.setText("Show")
        else:
            self._window.show()
            self._window.raise_()
            self._window.activateWindow()
            self._show_action.setText("Hide")

    def _on_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._toggle_window()

    def _quit(self):
        self._window._really_quit = True
        self._window._on_stop()
        from PySide6.QtWidgets import QApplication
        QApplication.quit()

    def set_connected(self):
        self._tray.setIcon(self._icons["connected"])
        self._tray.setToolTip("PyLanShare — Connected")

    def set_reconnecting(self):
        self._tray.setIcon(self._icons["reconnecting"])
        self._tray.setToolTip("PyLanShare — Reconnecting...")

    def set_disconnected(self):
        self._tray.setIcon(self._icons["disconnected"])
        self._tray.setToolTip("PyLanShare — Disconnected")

    def set_stopped(self):
        self._tray.setIcon(self._icons["stopped"])
        self._tray.setToolTip("PyLanShare — Stopped")

    def notify(self, title: str, message: str):
        self._tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 3000)
