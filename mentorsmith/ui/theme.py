"""Dark theme: colours and the application-wide stylesheet.

Kept in one place so the palette is consistent and so the learner can read
compiler output against a predictable background. Colours were chosen for
contrast on a dark background; the syntax colours are ordered so the most
common tokens are the most distinguishable.
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Palette
# --------------------------------------------------------------------------
BACKGROUND = "#1e1e1e"
SURFACE = "#252526"
SURFACE_ALT = "#2d2d30"
BORDER = "#3c3c3c"
FOREGROUND = "#d4d4d4"
MUTED = "#9d9d9d"

ACCENT = "#4fc1ff"          # links, selection, focus
SUCCESS = "#6a9955"
WARNING = "#d7ba7d"
ERROR = "#f14c4c"
INFO = "#569cd6"

# Syntax highlighting
SYNTAX_KEYWORD = "#569cd6"
SYNTAX_TYPE = "#4ec9b0"
SYNTAX_STRING = "#ce9178"
SYNTAX_NUMBER = "#b5cea8"
SYNTAX_COMMENT = "#6a9955"
SYNTAX_PREPROCESSOR = "#c586c0"
SYNTAX_FUNCTION = "#dcdcaa"
SYNTAX_OPERATOR = "#d4d4d4"

STYLESHEET = f"""
QWidget {{
    background-color: {BACKGROUND};
    color: {FOREGROUND};
    font-size: 13px;
}}

QMainWindow, QDialog {{
    background-color: {BACKGROUND};
}}

QGroupBox {{
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-top: 10px;
    padding-top: 10px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 4px;
    color: {MUTED};
}}

QPushButton {{
    background-color: {SURFACE_ALT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 6px 14px;
    color: {FOREGROUND};
}}

QPushButton:hover  {{ border-color: {ACCENT}; }}
QPushButton:pressed{{ background-color: {SURFACE}; }}
QPushButton:disabled {{ color: #5a5a5a; border-color: #2a2a2a; }}

QPushButton#primary {{
    background-color: {ACCENT};
    color: #101010;
    font-weight: bold;
    border: none;
}}
QPushButton#primary:hover {{ background-color: #6fd0ff; }}
QPushButton#primary:disabled {{ background-color: #3a5a6a; color: #707070; }}

QPushButton#danger {{
    border-color: {ERROR};
    color: {ERROR};
}}

QTextEdit, QPlainTextEdit, QListWidget, QTreeWidget, QLineEdit, QComboBox, QSpinBox {{
    background-color: {SURFACE};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 4px;
    selection-background-color: {ACCENT};
    selection-color: #101010;
}}

QLineEdit, QComboBox, QSpinBox {{ padding: 5px; }}

QListWidget::item, QTreeWidget::item {{
    padding: 6px 4px;
    border-radius: 3px;
}}
QListWidget::item:selected, QTreeWidget::item:selected {{
    background-color: {ACCENT};
    color: #101010;
}}
QListWidget::item:hover, QTreeWidget::item:hover {{
    background-color: {SURFACE_ALT};
}}

QHeaderView::section {{
    background-color: {SURFACE_ALT};
    border: none;
    border-bottom: 1px solid {BORDER};
    padding: 5px;
    color: {MUTED};
}}

QTabWidget::pane {{
    border: 1px solid {BORDER};
    border-radius: 4px;
}}
QTabBar::tab {{
    background: {SURFACE};
    padding: 7px 14px;
    border: 1px solid {BORDER};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}}
QTabBar::tab:selected {{ background: {SURFACE_ALT}; color: {ACCENT}; }}

QProgressBar {{
    border: 1px solid {BORDER};
    border-radius: 4px;
    background: {SURFACE};
    text-align: center;
    color: {FOREGROUND};
    height: 18px;
}}
QProgressBar::chunk {{ background-color: {INFO}; border-radius: 3px; }}

QLabel#title    {{ font-size: 20px; font-weight: bold; }}
QLabel#subtitle {{ color: {MUTED}; }}
QLabel#muted    {{ color: {MUTED}; }}
QLabel#error    {{ color: {ERROR}; }}
QLabel#success  {{ color: {SUCCESS}; }}
QLabel#warning  {{ color: {WARNING}; }}

QScrollBar:vertical {{
    background: {BACKGROUND};
    width: 11px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background: {BORDER};
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{ background: {MUTED}; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
QScrollBar:horizontal {{ background: {BACKGROUND}; height: 11px; }}
QScrollBar::handle:horizontal {{ background: {BORDER}; border-radius: 5px; min-width: 24px; }}

QSplitter::handle {{ background: {BORDER}; }}
QStatusBar {{ background: {SURFACE_ALT}; color: {MUTED}; }}
QStatusBar::item {{ border: none; }}

QToolTip {{
    background-color: {SURFACE_ALT};
    color: {FOREGROUND};
    border: 1px solid {ACCENT};
    padding: 4px;
}}
"""