"""Main window for PyLanShare GUI."""

import asyncio
import json
import os
import socket
import ssl
from pathlib import Path

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QRadioButton,
    QSystemTrayIcon,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from shared.theme import COLORS, ToolWindow, font, FONT_SIZE, FONT_SIZE_SMALL

from ..core.ignore import load_patterns
from ..net.discovery import get_lan_hosts
from ..net.receiver import Receiver
from ..net.sender import Sender
from ..net.sync_peer import SyncClient, SyncServer
from .ignore_dialog import IgnoreDialog
from .tray import TrayManager
from .worker import AsyncWorker

_SPEED_PRESETS = [
    ("Unlimited", 0),
    ("1 MB/s", 1_048_576),
    ("5 MB/s", 5_242_880),
    ("10 MB/s", 10_485_760),
    ("50 MB/s", 52_428_800),
]

_GROUP_STYLE = f"""
    QGroupBox {{
        border: 1px solid {COLORS['border']};
        border-radius: 8px;
        margin-top: 14px;
        padding: 20px 16px 12px 16px;
        font-weight: bold;
        color: {COLORS['primary']};
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 14px;
        padding: 0 8px;
    }}
"""


class MainWindow(ToolWindow):
    def __init__(self):
        super().__init__("PyLanShare", width=680, height=700)

        self._worker: AsyncWorker | None = None
        self._really_quit = False
        self._tray_notified_minimize = False
        self._build_ui()
        self._refresh_hosts()
        self._load_settings()

        # System tray
        self._tray: TrayManager | None = None
        if QSystemTrayIcon.isSystemTrayAvailable():
            self._tray = TrayManager(self)

    _SETTINGS_DIR = Path(os.environ.get("APPDATA", "")) / "AmMstools" / "pylanshare"
    _SETTINGS_FILE = _SETTINGS_DIR / "settings.json"

    def _load_settings(self):
        try:
            data = json.loads(self._SETTINGS_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if d := data.get("directory"):
            self._dir_edit.setText(d)
        if h := data.get("host"):
            self._host_combo.setCurrentText(h)
        if p := data.get("port"):
            self._port_edit.setText(str(p))
        if pw := data.get("password"):
            self._password_edit.setText(pw)
        role = data.get("role")
        if role == "receive":
            self._radio_receive.setChecked(True)
        elif role == "sync":
            self._radio_sync.setChecked(True)
        if "minimize_to_tray" in data:
            self._minimize_to_tray_action.setChecked(data["minimize_to_tray"])
        if "rate_limit" in data:
            for i, (_, val) in enumerate(_SPEED_PRESETS):
                if val == data["rate_limit"]:
                    self._speed_combo.setCurrentIndex(i)
                    break
        if data.get("use_tls"):
            self._tls_check.setChecked(True)
        if cert := data.get("tls_cert"):
            self._cert_edit.setText(cert)
        if key := data.get("tls_key"):
            self._key_edit.setText(key)

    def _save_settings(self):
        self._SETTINGS_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "directory": self._dir_edit.text().strip(),
            "host": self._host_combo.currentText().strip(),
            "port": self._port_edit.text().strip(),
            "password": self._password_edit.text().strip(),
            "role": ("send" if self._radio_send.isChecked()
                     else "sync" if self._radio_sync.isChecked()
                     else "receive"),
            "minimize_to_tray": self._minimize_to_tray_action.isChecked(),
            "rate_limit": _SPEED_PRESETS[self._speed_combo.currentIndex()][1],
            "use_tls": self._tls_check.isChecked(),
            "tls_cert": self._cert_edit.text().strip(),
            "tls_key": self._key_edit.text().strip(),
        }
        self._SETTINGS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _build_menu_bar(self):
        menu_bar = self.menuBar()
        menu_bar.setStyleSheet(f"""
            QMenuBar {{
                background-color: {COLORS['bg_light']};
                color: {COLORS['text']};
                border: none;
                padding: 2px;
            }}
            QMenuBar::item:selected {{
                background-color: {COLORS['accent']};
            }}
            QMenu {{
                background-color: {COLORS['bg_light']};
                color: {COLORS['text']};
                border: 1px solid {COLORS['accent']};
            }}
            QMenu::item:selected {{
                background-color: {COLORS['accent']};
            }}
            QMenu::indicator:checked {{
                background-color: {COLORS['primary']};
                border-radius: 3px;
            }}
        """)

        settings_menu = menu_bar.addMenu("Settings")

        self._minimize_to_tray_action = QAction("Minimize to tray on close", self, checkable=True)
        self._minimize_to_tray_action.setChecked(True)
        settings_menu.addAction(self._minimize_to_tray_action)

    def _build_ui(self):
        container = QWidget()
        container.setStyleSheet("background-color: transparent;")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(24, 8, 24, 16)
        container_layout.setSpacing(14)

        # -- Role selection --
        role_group = QGroupBox("Role")
        role_group.setStyleSheet(_GROUP_STYLE)
        role_layout = QHBoxLayout(role_group)
        role_layout.setContentsMargins(16, 8, 16, 12)
        role_layout.setSpacing(24)
        self._radio_send = QRadioButton("Send")
        self._radio_receive = QRadioButton("Receive")
        self._radio_sync = QRadioButton("Sync")
        self._radio_send.setChecked(True)
        role_layout.addWidget(self._radio_send)
        role_layout.addWidget(self._radio_receive)
        role_layout.addWidget(self._radio_sync)
        role_layout.addStretch()
        container_layout.addWidget(role_group)

        # -- Configuration --
        config_group = QGroupBox("Configuration")
        config_group.setStyleSheet(_GROUP_STYLE)
        grid = QGridLayout(config_group)
        grid.setContentsMargins(16, 12, 16, 12)
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(8)

        # Row 0: Directory
        grid.addWidget(self.make_label("Directory:"), 0, 0, Qt.AlignVCenter)
        self._dir_edit = QLineEdit()
        self._dir_edit.setPlaceholderText("Select folder to sync...")
        grid.addWidget(self._dir_edit, 0, 1, 1, 3)  # span 3 columns
        self._browse_btn = self.make_button("Browse", command=self._browse_dir, primary=False)
        self._browse_btn.setStyleSheet(self._browse_btn.styleSheet() + f"""
            QPushButton {{
                min-height: 0px;
                padding: 5px 14px;
            }}
        """)
        grid.addWidget(self._browse_btn, 0, 4, Qt.AlignVCenter)

        # Row 1: Password
        grid.addWidget(self.make_label("Password:"), 1, 0, Qt.AlignVCenter)
        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_edit.setPlaceholderText("Optional shared password...")
        grid.addWidget(self._password_edit, 1, 1, 1, 4)  # span to end

        # Row 2: Host + Port
        self._host_label = self.make_label("Receiver IP:")
        grid.addWidget(self._host_label, 2, 0, Qt.AlignVCenter)
        self._host_combo = QComboBox()
        self._host_combo.setEditable(True)
        self._host_combo.setCurrentText("localhost")
        self._host_combo.lineEdit().setPlaceholderText("IP or hostname...")
        self._refresh_hosts_btn = self.make_button("↻", command=self._refresh_hosts, primary=False)
        self._refresh_hosts_btn.setStyleSheet(self._refresh_hosts_btn.styleSheet() + """
            QPushButton { min-height: 0px; padding: 5px 8px; }
        """)
        self._refresh_hosts_btn.setToolTip("Scan LAN hosts")
        host_layout = QHBoxLayout()
        host_layout.setContentsMargins(0, 0, 0, 0)
        host_layout.setSpacing(4)
        host_layout.addWidget(self._host_combo, stretch=1)
        host_layout.addWidget(self._refresh_hosts_btn)
        grid.addLayout(host_layout, 2, 1, 1, 2)
        grid.addWidget(self.make_label("Port:"), 2, 3, Qt.AlignVCenter)
        self._port_edit = QLineEdit("8765")
        self._port_edit.setMaximumWidth(80)
        grid.addWidget(self._port_edit, 2, 4)

        # Row 3: Speed limit (sender only)
        self._speed_label = self.make_label("Speed limit:")
        grid.addWidget(self._speed_label, 3, 0, Qt.AlignVCenter)
        self._speed_combo = QComboBox()
        for label, _ in _SPEED_PRESETS:
            self._speed_combo.addItem(label)
        grid.addWidget(self._speed_combo, 3, 1, 1, 2)

        # Row 4: TLS
        self._tls_check = QCheckBox("Use TLS")
        grid.addWidget(self._tls_check, 4, 0, 1, 2)
        self._tls_check.toggled.connect(self._on_tls_toggled)

        # Row 5: TLS cert + key
        self._cert_label = self.make_label("Certificate:")
        grid.addWidget(self._cert_label, 5, 0, Qt.AlignVCenter)
        self._cert_edit = QLineEdit()
        self._cert_edit.setPlaceholderText("Path to .pem certificate...")
        grid.addWidget(self._cert_edit, 5, 1, 1, 3)
        self._cert_browse = self.make_button("...", command=self._browse_cert, primary=False)
        self._cert_browse.setStyleSheet(self._cert_browse.styleSheet() + """
            QPushButton { min-height: 0px; padding: 5px 10px; }
        """)
        grid.addWidget(self._cert_browse, 5, 4, Qt.AlignVCenter)

        self._key_label = self.make_label("Key:")
        grid.addWidget(self._key_label, 6, 0, Qt.AlignVCenter)
        self._key_edit = QLineEdit()
        self._key_edit.setPlaceholderText("Path to .pem key...")
        grid.addWidget(self._key_edit, 6, 1, 1, 3)
        self._key_browse = self.make_button("...", command=self._browse_key, primary=False)
        self._key_browse.setStyleSheet(self._key_browse.styleSheet() + """
            QPushButton { min-height: 0px; padding: 5px 10px; }
        """)
        grid.addWidget(self._key_browse, 6, 4, Qt.AlignVCenter)

        # Hide TLS fields by default
        self._set_tls_fields_visible(False)

        # Row 7: IP hint
        local_ips = self._get_local_ips()
        if local_ips:
            ip_hint = self.make_label(f"Your IP: {', '.join(local_ips)}", dim=True)
            ip_hint.setFont(font(FONT_SIZE_SMALL))
            grid.addWidget(ip_hint, 7, 1, 1, 4)

        container_layout.addWidget(config_group)

        # -- Buttons --
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.setContentsMargins(0, 4, 0, 4)
        self._start_btn = self.make_button("Start", command=self._on_toggle)
        self._is_running = False

        self._ignore_btn = self.make_button("Ignore Patterns", command=self._on_ignore_patterns, primary=False)
        self._sync_btn = self.make_button("Force Sync", command=self._on_force_sync, primary=False)
        self._sync_btn.setEnabled(False)

        btn_row.addWidget(self._start_btn)
        btn_row.addStretch()
        btn_row.addWidget(self._ignore_btn)
        btn_row.addWidget(self._sync_btn)
        container_layout.addLayout(btn_row)

        # -- Progress --
        progress_container = QVBoxLayout()
        progress_container.setSpacing(4)
        progress_container.setContentsMargins(0, 0, 0, 0)
        self._progress_label = self.make_label("", dim=True)
        self._progress_label.setFont(font(FONT_SIZE_SMALL))
        self._progress_label.setVisible(False)
        progress_container.addWidget(self._progress_label)
        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        self._progress_bar.setFixedHeight(6)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                border-radius: 3px;
                background-color: {COLORS['bg_light']};
            }}
            QProgressBar::chunk {{
                background-color: {COLORS['success']};
                border-radius: 3px;
            }}
        """)
        progress_container.addWidget(self._progress_bar)
        container_layout.addLayout(progress_container)

        # Session counters (reset on start)
        self._stats = {
            "files_sent": 0, "files_recv": 0, "files_del": 0,
            "bytes_sent": 0, "bytes_recv": 0,
        }

        # -- Log header with inline stats --
        log_header = QHBoxLayout()
        log_header.setContentsMargins(0, 0, 0, 0)
        log_label = self.make_label("Log", dim=True)
        log_label.setFont(font(FONT_SIZE_SMALL, bold=True))
        log_label.setStyleSheet(f"color: {COLORS['text_dim']}; padding: 0;")
        log_header.addWidget(log_label)
        log_header.addStretch()
        self._stats_label = self.make_label("", dim=True)
        self._stats_label.setFont(font(FONT_SIZE_SMALL))
        log_header.addWidget(self._stats_label)
        container_layout.addLayout(log_header)

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._log.setMinimumHeight(200)
        self._log.setStyleSheet(f"""
            QTextEdit {{
                background-color: {COLORS['bg_light']};
                border: 1px solid {COLORS['border']};
                border-radius: 6px;
                padding: 8px;
                font-family: "Cascadia Code", "Consolas", monospace;
                font-size: {FONT_SIZE_SMALL}px;
            }}
        """)
        container_layout.addWidget(self._log, stretch=1)

        self.add_widget(container)

        # -- Status --
        self._status_label = self.add_status_bar()
        self._status_label.setText("Ready")

        # Role toggle
        self._radio_send.toggled.connect(self._on_role_changed)
        self._radio_receive.toggled.connect(self._on_role_changed)
        self._radio_sync.toggled.connect(self._on_role_changed)
        self._on_role_changed()

    @staticmethod
    def _get_local_ips() -> list[str]:
        ips = []
        try:
            for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
                ip = info[4][0]
                if ip != "127.0.0.1" and ip not in ips:
                    ips.append(ip)
        except OSError:
            pass
        return ips

    def _on_role_changed(self):
        is_send = self._radio_send.isChecked()
        is_sync = self._radio_sync.isChecked()
        show_host = is_send or is_sync
        self._host_combo.setEnabled(show_host)
        self._refresh_hosts_btn.setVisible(show_host)
        self._speed_label.setVisible(show_host)
        self._speed_combo.setVisible(show_host)
        if is_sync:
            self._host_label.setText("Server IP:")
            self._host_combo.lineEdit().setPlaceholderText(
                "0.0.0.0 = listen, or enter server IP..."
            )
        else:
            self._host_label.setText("Receiver IP:")
            self._host_combo.lineEdit().setPlaceholderText("IP or hostname...")
        if not show_host:
            self._host_combo.setCurrentText("0.0.0.0")
        elif is_sync and self._host_combo.currentText() == "localhost":
            self._host_combo.setCurrentText("0.0.0.0")
        elif is_send and self._host_combo.currentText() == "0.0.0.0":
            self._host_combo.setCurrentText("localhost")

    def _refresh_hosts(self):
        current = self._host_combo.currentText()
        self._host_combo.clear()
        self._host_combo.addItem("localhost")
        for ip in get_lan_hosts():
            if self._host_combo.findText(ip) == -1:
                self._host_combo.addItem(ip)
        # Restore previous value
        self._host_combo.setCurrentText(current)

    def _browse_dir(self):
        d = QFileDialog.getExistingDirectory(self, "Select Directory")
        if d:
            self._dir_edit.setText(d)

    def _set_tls_fields_visible(self, visible: bool):
        for w in (self._cert_label, self._cert_edit, self._cert_browse,
                  self._key_label, self._key_edit, self._key_browse):
            w.setVisible(visible)

    def _on_tls_toggled(self, checked: bool):
        self._set_tls_fields_visible(checked)

    def _browse_cert(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Certificate", "", "PEM files (*.pem);;All files (*)")
        if f:
            self._cert_edit.setText(f)

    def _browse_key(self):
        f, _ = QFileDialog.getOpenFileName(self, "Select Key", "", "PEM files (*.pem);;All files (*)")
        if f:
            self._key_edit.setText(f)

    def _build_ssl_context(self) -> ssl.SSLContext | None:
        if not self._tls_check.isChecked():
            return None
        cert = self._cert_edit.text().strip()
        key = self._key_edit.text().strip()
        if not cert:
            self._append_log("Error: TLS enabled but no certificate path set")
            return None
        host = self._host_combo.currentText().strip()
        is_client = self._radio_send.isChecked() or (
            self._radio_sync.isChecked() and host != "0.0.0.0"
        )
        if is_client:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            ctx.load_cert_chain(certfile=cert, keyfile=key or None)
        else:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            ctx.load_cert_chain(certfile=cert, keyfile=key or None)
        return ctx

    def _on_ignore_patterns(self):
        dir_path = self._dir_edit.text().strip()
        if not dir_path:
            self._append_log("Select a directory first to configure ignore patterns")
            return
        dialog = IgnoreDialog(Path(dir_path), parent=self)
        dialog.exec()

    def _set_start_btn_color(self, color: str):
        self._start_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: {COLORS['text']};
            }}
            QPushButton:hover {{
                background-color: {color};
            }}
        """)

    @Slot(bool)
    def _on_connected_changed(self, connected: bool):
        if connected:
            self._set_start_btn_color(COLORS['success'])
            if self._tray:
                self._tray.set_connected()
                self._tray.notify("Connected", "Sync started")
        else:
            self._set_start_btn_color(COLORS['error'])
            if self._tray:
                self._tray.set_disconnected()
                self._tray.notify("Disconnected", "Connection lost")

    @Slot(bool)
    def _on_reconnecting(self, reconnecting: bool):
        if reconnecting:
            self._set_start_btn_color(COLORS['warning'])
            if self._tray:
                self._tray.set_reconnecting()

    @staticmethod
    def _format_bytes(n: int) -> str:
        if n < 1024:
            return f"{n} B"
        if n < 1024 * 1024:
            return f"{n / 1024:.1f} KB"
        if n < 1024 * 1024 * 1024:
            return f"{n / (1024 * 1024):.1f} MB"
        return f"{n / (1024 * 1024 * 1024):.2f} GB"

    def _refresh_stats(self):
        s = self._stats
        total_bytes = s["bytes_sent"] + s["bytes_recv"]
        total_files = s["files_sent"] + s["files_recv"]
        parts = []
        if total_files:
            parts.append(f"{total_files} files")
        if total_bytes:
            parts.append(self._format_bytes(total_bytes))
        if s["files_del"]:
            parts.append(f"{s['files_del']} deleted")
        self._stats_label.setText("  |  ".join(parts))

    def _reset_stats(self):
        for k in self._stats:
            self._stats[k] = 0
        self._stats_label.setText("")

    @Slot(str)
    def _append_log(self, text: str):
        self._log.append(text)
        # Track session stats from log messages
        if text.startswith("Sent: "):
            self._stats["files_sent"] += 1
            self._refresh_stats()
        elif text.startswith("Received: "):
            self._stats["files_recv"] += 1
            self._refresh_stats()
        elif text.startswith("Deleted: ") or text.startswith("Delete: "):
            self._stats["files_del"] += 1
            self._refresh_stats()

    @Slot(str)
    def _update_status(self, text: str):
        self._status_label.setText(text)

    @Slot(str, int, int)
    def _update_progress(self, filename: str, current: int, total: int):
        self._progress_bar.setVisible(True)
        self._progress_label.setVisible(True)
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(current)
        self._progress_label.setText(f"{filename}: {current:,} / {total:,} bytes")
        if current >= total:
            self._progress_bar.setVisible(False)
            self._progress_label.setVisible(False)
            # Track transferred bytes (sent or received based on status text)
            status = self._status_label.text()
            if "Sending" in status:
                self._stats["bytes_sent"] += total
            elif "Receiving" in status:
                self._stats["bytes_recv"] += total
            self._refresh_stats()

    def _on_toggle(self):
        if self._is_running:
            self._on_stop()
        else:
            self._on_start()

    def _on_start(self):
        dir_path = self._dir_edit.text().strip()
        if not dir_path:
            self._append_log("Error: select a directory first")
            return

        port = int(self._port_edit.text().strip() or "8765")
        host = self._host_combo.currentText().strip()
        is_send = self._radio_send.isChecked()
        base_dir = Path(dir_path)
        token = self._password_edit.text().strip() or None
        ignore = load_patterns(base_dir)

        self._save_settings()

        ssl_ctx = self._build_ssl_context()
        rate_limit = _SPEED_PRESETS[self._speed_combo.currentIndex()][1]

        if is_send:
            async def run_sender(worker: AsyncWorker):
                sender = Sender(base_dir, host, port, watch=True,
                                token=token, ignore_patterns=ignore,
                                rate_limit=rate_limit, ssl_context=ssl_ctx)
                sender.on_log.append(lambda m: worker.log_signal.emit(m))
                sender.on_status.append(lambda m: worker.status_signal.emit(m))
                sender.on_progress.append(lambda f, c, t: worker.progress_signal.emit(f, c, t))
                sender.on_connected.append(lambda c: worker.connected_signal.emit(c))
                sender.on_reconnecting.append(lambda r: worker.reconnecting_signal.emit(r))
                worker._service = sender
                await sender.run()

            self._start_worker(run_sender)
        elif self._radio_sync.isChecked():
            is_server = (host == "0.0.0.0")

            def _wire_sync(service, worker):
                service.on_log.append(lambda m: worker.log_signal.emit(m))
                service.on_status.append(lambda m: worker.status_signal.emit(m))
                service.on_progress.append(lambda f, c, t: worker.progress_signal.emit(f, c, t))
                service.on_connected.append(lambda c: worker.connected_signal.emit(c))
                service.on_reconnecting.append(lambda r: worker.reconnecting_signal.emit(r))

            if is_server:
                async def run_sync_server(worker: AsyncWorker):
                    server = SyncServer(base_dir, host, port,
                                        token=token, ignore_patterns=ignore,
                                        rate_limit=rate_limit, ssl_context=ssl_ctx)
                    _wire_sync(server, worker)
                    worker._service = server
                    await server.run()

                self._start_worker(run_sync_server)
            else:
                async def run_sync_client(worker: AsyncWorker):
                    client = SyncClient(base_dir, host, port,
                                        token=token, ignore_patterns=ignore,
                                        rate_limit=rate_limit, ssl_context=ssl_ctx)
                    _wire_sync(client, worker)
                    worker._service = client
                    await client.run()

                self._start_worker(run_sync_client)
        else:
            async def run_receiver(worker: AsyncWorker):
                receiver = Receiver(base_dir, host, port,
                                    token=token, ignore_patterns=ignore,
                                    ssl_context=ssl_ctx)
                receiver.on_log.append(lambda m: worker.log_signal.emit(m))
                receiver.on_status.append(lambda m: worker.status_signal.emit(m))
                receiver.on_progress.append(lambda f, c, t: worker.progress_signal.emit(f, c, t))
                receiver.on_connected.append(lambda c: worker.connected_signal.emit(c))
                worker._service = receiver
                await receiver.run()

            self._start_worker(run_receiver)

    def _start_worker(self, coro_factory):
        self._reset_stats()
        self._log.clear()
        self._worker = AsyncWorker(coro_factory)
        self._worker.log_signal.connect(self._append_log)
        self._worker.status_signal.connect(self._update_status)
        self._worker.progress_signal.connect(self._update_progress)
        self._worker.connected_signal.connect(self._on_connected_changed)
        self._worker.reconnecting_signal.connect(self._on_reconnecting)
        self._worker.finished_signal.connect(self._on_worker_finished)
        self._worker.start()
        self._is_running = True

        self._start_btn.setText("Stop")
        self._set_start_btn_color(COLORS['success'])
        self._sync_btn.setEnabled(
            self._radio_send.isChecked() or self._radio_sync.isChecked()
        )
        self._radio_send.setEnabled(False)
        self._radio_receive.setEnabled(False)
        self._radio_sync.setEnabled(False)

    def _on_stop(self):
        if self._worker:
            self._worker.stop_service()

    def _on_force_sync(self):
        if self._worker and self._worker._loop and self._worker._service:
            service = self._worker._service
            if hasattr(service, "force_sync"):
                asyncio.run_coroutine_threadsafe(service.force_sync(), self._worker._loop)

    @Slot()
    def _on_worker_finished(self):
        self._is_running = False
        self._start_btn.setText("Start")
        self._set_start_btn_color(COLORS['primary'])
        self._sync_btn.setEnabled(False)
        self._radio_send.setEnabled(True)
        self._radio_receive.setEnabled(True)
        self._radio_sync.setEnabled(True)
        self._worker = None
        self._status_label.setText("Stopped")
        if self._tray:
            self._tray.set_stopped()

    def closeEvent(self, event):
        self._save_settings()
        minimize = self._minimize_to_tray_action.isChecked()
        if self._really_quit or not self._tray or not minimize:
            # Actually close
            self._on_stop()
            if self._worker:
                self._worker.wait(3000)
            super().closeEvent(event)
            QApplication.instance().quit()
        else:
            # Minimize to tray
            self.hide()
            if not self._tray_notified_minimize:
                self._tray.notify("PyLanShare", "Minimized to tray. Double-click to reopen.")
                self._tray_notified_minimize = True
            event.ignore()
