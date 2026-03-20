"""Tema condiviso e finestra base per tutti i tool di ammstools (PySide6)."""

from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QLabel, QPushButton,
    QStatusBar, QMenuBar, QMenu, QMessageBox,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QAction, QActionGroup

_ASSETS = Path(__file__).resolve().parent / "assets"

# ── Palette ──────────────────────────────────────────────────────────────
COLORS = {
    "bg":            "#121212",   # sfondo principale
    "bg_light":      "#1e1e1e",   # superfici, card, input
    "bg_elevated":   "#252525",   # elementi sollevati (hover, popup)
    "accent":        "#2a2a2a",   # bordi sottili, separatori
    "border":        "#333333",   # bordi input/combo
    "primary":       "#3b82f6",   # blu elettrico – azioni principali
    "primary_hover": "#2563eb",   # blu più scuro – hover
    "text":          "#f0f0f0",   # testo principale
    "text_dim":      "#71717a",   # testo secondario
    "success":       "#22c55e",
    "error":         "#ef4444",
    "warning":       "#eab308",
}

# ── Tipografia ───────────────────────────────────────────────────────────
FONT_FAMILY = "Segoe UI"
FONT_SIZE = 14
FONT_SIZE_TITLE = 22
FONT_SIZE_SMALL = 12

# ── Stylesheet base ─────────────────────────────────────────────────────
_CHEVRON = (_ASSETS / "chevron-down.svg").as_posix()

_BASE_STYLE = f"""
    /* ---- globale ---- */
    QWidget {{
        background-color: {COLORS["bg"]};
        color: {COLORS["text"]};
        font-family: "{FONT_FAMILY}";
        font-size: {FONT_SIZE}px;
    }}

    QLabel {{
        background-color: transparent;
    }}

    /* ---- pulsanti ---- */
    QPushButton {{
        border: none;
        border-radius: 8px;
        padding: 6px 18px;
        font-weight: 600;
        font-size: {FONT_SIZE}px;
        min-height: 30px;
    }}

    /* ---- input ---- */
    QLineEdit, QTextEdit, QPlainTextEdit {{
        background-color: {COLORS["bg_light"]};
        color: {COLORS["text"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 6px;
        padding: 5px 10px;
        font-size: {FONT_SIZE}px;
        min-height: 28px;
        selection-background-color: {COLORS["primary"]};
    }}
    QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {{
        border-color: {COLORS["primary"]};
    }}

    /* ---- scroll area ---- */
    QScrollArea, QScrollArea > QWidget > QWidget {{
        background-color: transparent;
    }}

    /* ---- scrollbar verticale ---- */
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        border-radius: 4px;
    }}
    QScrollBar::handle:vertical {{
        background: {COLORS["accent"]};
        border-radius: 4px;
        min-height: 24px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {COLORS["border"]};
    }}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    /* ---- scrollbar orizzontale ---- */
    QScrollBar:horizontal {{
        background: transparent;
        height: 8px;
        border-radius: 4px;
    }}
    QScrollBar::handle:horizontal {{
        background: {COLORS["accent"]};
        border-radius: 4px;
        min-width: 24px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {COLORS["border"]};
    }}
    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
        width: 0px;
    }}

    /* ---- checkbox ---- */
    QCheckBox {{
        color: {COLORS["text"]};
        spacing: 8px;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 2px solid {COLORS["border"]};
        border-radius: 4px;
        background: {COLORS["bg_light"]};
    }}
    QCheckBox::indicator:hover {{
        border-color: {COLORS["primary"]};
    }}
    QCheckBox::indicator:checked {{
        background: {COLORS["primary"]};
        border-color: {COLORS["primary"]};
    }}

    /* ---- radio button ---- */
    QRadioButton {{
        color: {COLORS["text"]};
        spacing: 8px;
    }}
    QRadioButton::indicator {{
        width: 14px;
        height: 14px;
        border: 2px solid {COLORS["border"]};
        border-radius: 9px;
        background: transparent;
    }}
    QRadioButton::indicator:hover {{
        border-color: {COLORS["primary"]};
    }}
    QRadioButton::indicator:checked {{
        background: {COLORS["primary"]};
        border-color: {COLORS["primary"]};
    }}

    /* ---- combobox ---- */
    QComboBox {{
        background-color: {COLORS["bg_light"]};
        color: {COLORS["text"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 6px;
        padding: 5px 10px;
    }}
    QComboBox:hover {{
        border-color: {COLORS["primary"]};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox::down-arrow {{
        image: url({_CHEVRON});
        width: 12px;
        height: 12px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {COLORS["bg_elevated"]};
        color: {COLORS["text"]};
        selection-background-color: {COLORS["primary"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 4px;
    }}

    /* ---- table ---- */
    QTableView, QTableWidget {{
        background-color: {COLORS["bg_light"]};
        color: {COLORS["text"]};
        border: 1px solid {COLORS["border"]};
        gridline-color: {COLORS["accent"]};
        selection-background-color: {COLORS["primary"]};
        selection-color: {COLORS["text"]};
        alternate-background-color: {COLORS["bg_elevated"]};
    }}
    QTableView::item:selected, QTableWidget::item:selected {{
        background-color: {COLORS["primary"]};
        color: {COLORS["text"]};
    }}
    QTableView::item:hover, QTableWidget::item:hover {{
        background-color: {COLORS["bg_elevated"]};
    }}
    QHeaderView::section {{
        background-color: {COLORS["bg"]};
        color: {COLORS["text"]};
        border: 1px solid {COLORS["accent"]};
        padding: 4px 8px;
        font-weight: 600;
    }}
    QHeaderView::section:hover {{
        background-color: {COLORS["bg_elevated"]};
    }}
    QTableCornerButton::section {{
        background-color: {COLORS["bg"]};
        border: 1px solid {COLORS["accent"]};
    }}

    /* ---- tooltip ---- */
    QToolTip {{
        background-color: {COLORS["bg_elevated"]};
        color: {COLORS["text"]};
        border: 1px solid {COLORS["border"]};
        border-radius: 4px;
        padding: 4px 8px;
    }}
"""


def font(size: int = FONT_SIZE, bold: bool = False) -> QFont:
    """Crea un QFont con lo stile del tema."""
    f = QFont(FONT_FAMILY, size)
    if bold:
        f.setBold(True)
    return f


class ToolWindow(QMainWindow):
    """Finestra base per tutti i tool di ammstools."""

    def __init__(self, title: str, width: int = 600, height: int = 400):
        super().__init__()

        self.setWindowTitle(f"AmMstools — {title}")
        self.setMinimumSize(width, height)
        self.resize(width, height)
        self.setStyleSheet(_BASE_STYLE)
        self._apply_dark_titlebar()

        # Menu bar
        self._build_menu_bar()

        # Central widget con layout verticale
        self._central = QWidget()
        self.setCentralWidget(self._central)
        self._layout = QVBoxLayout(self._central)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)


    def _apply_dark_titlebar(self):
        """Forza la titlebar scura su Windows 10/11 tramite DWM API."""
        try:
            import ctypes
            hwnd = int(self.winId())
            dwmapi = ctypes.windll.dwmapi
            value = ctypes.c_int(1)
            result = dwmapi.DwmSetWindowAttribute(
                hwnd, 20, ctypes.byref(value), ctypes.sizeof(value)
            )
            if result != 0:
                dwmapi.DwmSetWindowAttribute(
                    hwnd, 19, ctypes.byref(value), ctypes.sizeof(value)
                )
        except Exception:
            pass

    def _build_menu_bar(self):
        """Crea la menu bar con Settings > Language."""
        from shared.i18n import available_locales, get_locale, set_locale

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

        # Language submenu
        lang_menu = settings_menu.addMenu("Language")
        lang_group = QActionGroup(self)
        lang_group.setExclusive(True)

        current = get_locale()
        lang_names = {"en": "English", "it": "Italiano", "de": "Deutsch",
                      "es": "Español", "fr": "Français", "pt": "Português"}

        for code in available_locales():
            label = lang_names.get(code, code.upper())
            action = QAction(label, self, checkable=True)
            action.setChecked(code == current)
            action.triggered.connect(lambda checked, c=code: self._on_language_change(c))
            lang_group.addAction(action)
            lang_menu.addAction(action)

    def _on_language_change(self, lang_code: str):
        from shared.i18n import set_locale
        from shared.config import set as config_set
        set_locale(lang_code)
        config_set("language", lang_code)
        QMessageBox.information(
            self, "Language",
            "Language changed. Restart the application to apply."
        )

    def add_status_bar(self) -> QLabel:
        """Aggiunge una barra di stato in fondo alla finestra e ritorna la label."""
        status = QLabel("")
        status.setFont(font(FONT_SIZE_SMALL))
        status.setStyleSheet(
            f"color: {COLORS['text_dim']}; padding: 0 12px 8px 12px;"
        )
        self._layout.addWidget(status)
        return status

    def add_widget(self, widget: QWidget):
        """Aggiunge un widget al layout centrale."""
        self._layout.addWidget(widget)

    def add_layout(self, layout):
        """Aggiunge un sub-layout al layout centrale."""
        self._layout.addLayout(layout)

    def make_button(
        self, text: str, command=None, primary: bool = True, danger: bool = False, **kwargs
    ) -> QPushButton:
        """Crea un bottone con lo stile del tema."""
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
                color: {COLORS["text"]};
            }}
            QPushButton:hover {{
                background-color: {hover};
            }}
        """)
        if command:
            btn.clicked.connect(command)
        return btn

    def make_label(self, text: str, dim: bool = False, **kwargs) -> QLabel:
        """Crea una label con lo stile del tema."""
        lbl = QLabel(text)
        lbl.setFont(font(FONT_SIZE))
        color = COLORS["text_dim"] if dim else COLORS["text"]
        lbl.setStyleSheet(f"color: {color};")
        return lbl
