"""Dialog for editing ignore patterns."""

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from shared.theme import COLORS, font, FONT_SIZE, FONT_SIZE_SMALL

from ..core.ignore import DEFAULT_PATTERNS, load_patterns, save_patterns

_DIALOG_STYLE = f"""
    QDialog {{
        background-color: {COLORS['bg']};
        color: {COLORS['text']};
    }}
    QPlainTextEdit {{
        background-color: {COLORS['bg_light']};
        color: {COLORS['text']};
        border: 1px solid {COLORS['border']};
        border-radius: 6px;
        padding: 8px;
        font-family: "Cascadia Code", "Consolas", monospace;
        font-size: {FONT_SIZE}px;
    }}
    QPlainTextEdit:focus {{
        border-color: {COLORS['primary']};
    }}
    QLabel {{
        background-color: transparent;
        color: {COLORS['text_dim']};
    }}
"""


def _make_btn(text: str, primary: bool = True, danger: bool = False) -> QPushButton:
    btn = QPushButton(text)
    btn.setFont(font(FONT_SIZE, bold=True))
    if danger:
        bg, hover = COLORS["error"], "#dc2626"
    elif primary:
        bg, hover = COLORS["primary"], COLORS["primary_hover"]
    else:
        bg, hover = COLORS["accent"], COLORS["bg_elevated"]
    btn.setStyleSheet(f"""
        QPushButton {{
            background-color: {bg};
            color: {COLORS['text']};
            border: none;
            border-radius: 8px;
            padding: 6px 18px;
            font-weight: 600;
            min-height: 30px;
        }}
        QPushButton:hover {{
            background-color: {hover};
        }}
    """)
    return btn


class IgnoreDialog(QDialog):
    def __init__(self, watch_dir: Path, parent=None):
        super().__init__(parent)
        self._watch_dir = watch_dir
        self.setWindowTitle("Ignore Patterns")
        self.setMinimumSize(450, 400)
        self.setStyleSheet(_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        hint = QLabel("One pattern per line. Supports wildcards: *, ?\nExample: *.pyc, __pycache__, build/*.log")
        hint.setFont(font(FONT_SIZE_SMALL))
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self._editor = QPlainTextEdit()
        patterns = load_patterns(watch_dir)
        self._editor.setPlainText("\n".join(patterns))
        layout.addWidget(self._editor, stretch=1)

        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)

        reset_btn = _make_btn("Reset Defaults", primary=False)
        reset_btn.clicked.connect(self._reset)
        btn_row.addWidget(reset_btn)

        btn_row.addStretch()

        cancel_btn = _make_btn("Cancel", primary=False)
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)

        save_btn = _make_btn("Save")
        save_btn.clicked.connect(self._save)
        btn_row.addWidget(save_btn)

        layout.addLayout(btn_row)

    def _reset(self):
        self._editor.setPlainText("\n".join(DEFAULT_PATTERNS))

    def _save(self):
        text = self._editor.toPlainText()
        patterns = [line.strip() for line in text.splitlines() if line.strip()]
        save_patterns(self._watch_dir, patterns)
        self.accept()
