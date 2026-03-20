"""Barra singola per visualizzare latenza DNS."""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt
from shared.theme import COLORS, font, FONT_SIZE, FONT_SIZE_SMALL


class LatencyBar(QWidget):

    def __init__(self, parent=None, name: str = "", ip: str = "",
                 ms: float | None = None, max_ms: float = 200):
        super().__init__(parent)
        self.setFixedHeight(28)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Nome
        name_lbl = QLabel(name)
        name_lbl.setFont(font(FONT_SIZE, bold=True))
        name_lbl.setFixedWidth(130)
        layout.addWidget(name_lbl)

        # Valore ms
        if ms is not None:
            ms_text = f"{ms:.0f}ms"
            color = COLORS["success"] if ms < 50 else COLORS["warning"] if ms < 100 else COLORS["error"]
        else:
            ms_text = "timeout"
            color = COLORS["text_dim"]

        ms_lbl = QLabel(ms_text)
        ms_lbl.setFont(font(FONT_SIZE_SMALL))
        ms_lbl.setStyleSheet(f"color: {color};")
        ms_lbl.setFixedWidth(60)
        ms_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(ms_lbl)

        # Barra
        bar_bg = QFrame()
        bar_bg.setFixedHeight(14)
        bar_bg.setStyleSheet(
            f"background-color: {COLORS['bg_light']}; border-radius: 4px;"
        )
        layout.addWidget(bar_bg, stretch=1)

        if ms is not None:
            ratio = min(ms / max_ms, 1.0)
            bar = QFrame(bar_bg)
            bar.setStyleSheet(f"background-color: {color}; border-radius: 4px;")
            bar.setFixedHeight(14)
            # Width will be set after layout
            bar_bg.resizeEvent = lambda e, b=bar, r=ratio: b.setFixedWidth(int(e.size().width() * r))

        # IP
        ip_lbl = QLabel(ip)
        ip_lbl.setFont(font(FONT_SIZE_SMALL))
        ip_lbl.setStyleSheet(f"color: {COLORS['text_dim']};")
        ip_lbl.setFixedWidth(100)
        ip_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(ip_lbl)
