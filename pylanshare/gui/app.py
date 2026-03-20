"""Application entry point for the GUI."""

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QSystemTrayIcon

from .window import MainWindow

_ICON_PATH = Path(__file__).resolve().parent.parent / "assets" / "icon.png"


def run_gui():
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(str(_ICON_PATH)))

    # Keep running when window is hidden to tray
    if QSystemTrayIcon.isSystemTrayAvailable():
        app.setQuitOnLastWindowClosed(False)

    window = MainWindow()
    window.show()
    sys.exit(app.exec())
