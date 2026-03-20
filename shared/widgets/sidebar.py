"""Lista selezionabile verticale con evidenziazione dell'elemento attivo."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton
from PySide6.QtCore import Qt
from shared.theme import COLORS, font, FONT_SIZE


class Sidebar(QWidget):

    def __init__(self, parent=None, items: list[str] = None, on_select=None, width: int = 200):
        super().__init__(parent)
        self.setFixedWidth(width)
        self.setStyleSheet(f"background-color: {COLORS['bg_light']};")

        self._on_select = on_select
        self._buttons: list[QPushButton] = []
        self._selected_index: int = -1

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(1)
        self._layout.addStretch()

        if items:
            self._add_buttons(items)
            self.select(0, _notify=False)

    def _add_buttons(self, items: list[str]):
        # Remove stretch, add buttons, re-add stretch
        stretch = self._layout.takeAt(self._layout.count() - 1)
        for i, item in enumerate(items):
            btn = QPushButton(item)
            btn.setFont(font(FONT_SIZE))
            btn.setFixedHeight(38)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(self._btn_style(selected=False))
            btn.clicked.connect(lambda checked, idx=i: self.select(idx))
            self._layout.addWidget(btn)
            self._buttons.append(btn)
        self._layout.addStretch()

    def _btn_style(self, selected: bool) -> str:
        if selected:
            return f"""
                QPushButton {{
                    background-color: {COLORS["accent"]};
                    color: {COLORS["primary"]};
                    text-align: left;
                    padding: 0 12px;
                    border: none;
                    border-radius: 0;
                }}
            """
        return f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS["text"]};
                text-align: left;
                padding: 0 12px;
                border: none;
                border-radius: 0;
            }}
            QPushButton:hover {{
                background-color: {COLORS["accent"]};
            }}
        """

    def select(self, index: int, _notify: bool = True):
        if self._selected_index == index:
            return

        if 0 <= self._selected_index < len(self._buttons):
            self._buttons[self._selected_index].setStyleSheet(self._btn_style(False))

        self._selected_index = index
        if 0 <= index < len(self._buttons):
            self._buttons[index].setStyleSheet(self._btn_style(True))

        if _notify and self._on_select:
            self._on_select(index, self._buttons[index].text())

    @property
    def selected(self) -> str | None:
        if 0 <= self._selected_index < len(self._buttons):
            return self._buttons[self._selected_index].text()
        return None

    def update_items(self, items: list[str]):
        for btn in self._buttons:
            btn.deleteLater()
        self._buttons.clear()
        self._selected_index = -1
        # Clear layout except stretch
        while self._layout.count() > 0:
            self._layout.takeAt(0)
        self._layout.addStretch()
        self._add_buttons(items)
        if items:
            self.select(0, _notify=False)
