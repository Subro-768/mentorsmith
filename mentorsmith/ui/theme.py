"""Multi-theme engine — built from scratch.

Three themes available:
  - paper       : Warm off-white, low contrast, muted terracotta (default).
  - light       : Clean white base with warm orange accent.
  - dark_orange : Deep black/charcoal base with rich amber-orange accent.
  - dark_purple : Original deep navy + violet/purple accent (legacy).

Usage:
    from mentorsmith.ui import theme
    window.setStyleSheet(theme.get_stylesheet("dark_orange"))
    # or use the active stylesheet directly (defaults to dark_orange):
    window.setStyleSheet(theme.STYLESHEET)

    To switch at runtime call apply_theme(window, "light").
"""

from __future__ import annotations

from typing import Any

# ---------------------------------------------------------------------------
# Theme definitions — all palette tokens per theme
# ---------------------------------------------------------------------------

#: The theme the app starts in.
#:
#: Paper, not the dark one. The dark themes looked striking but were tiring
#: over a long study session, and a learner spends hours in here.
DEFAULT_THEME = "paper"

_PALETTES: dict[str, dict[str, str]] = {

    # ── Dark Orange / Black ──────────────────────────────────────────────
    "dark_orange": {
        "BASE":          "#0a0a0b",    # Near-black background
        "SURFACE":       "#141414",    # Card / panel background
        "SURFACE_ALT":   "#1a1a1a",    # Slightly elevated surfaces
        "SURFACE_HOV":   "#212121",    # Hover states
        "BORDER":        "#2e2e2e",    # Dividers, input borders
        "BORDER_SUB":    "#1e1e1e",    # Subtle secondary borders

        "FOREGROUND":    "#f0ece4",    # Primary text (warm white)
        "MUTED":         "#7a7069",    # Secondary / helper text
        "PLACEHOLDER":   "#4a4540",    # Placeholder text

        # Accent — amber / orange
        "ACCENT":        "#e8650a",    # Primary accent (deep amber-orange)
        "ACCENT_LIGHT":  "#f4934a",    # Hover / lighter variant
        "ACCENT_ALT":    "#c24d08",    # Gradient endpoint (darker burnt orange)
        "ACCENT_TEXT":   "#fff5eb",    # Text on accent backgrounds

        # Sidebar active background (dark transparent orange)
        "NAV_ACTIVE_BG": "#2b1800",
        "NAV_ACTIVE_BG_HOV": "#3a2000",

        # List / tree item selected
        "LIST_SEL_BG":   "#2b1800",

        # Primary button disabled
        "BTN_DISABLED_BG": "#3a2000",
        "BTN_DISABLED_FG": "#8a5530",

        # Pressed accent on primary button hover text
        "PRIMARY_HOVER_FG": "#1a0800",

        # Secondary — warm amber
        "CYAN":          "#f0a500",
        "CYAN_LIGHT":    "#ffc840",

        # Semantic (unchanged across themes)
        "SUCCESS":       "#3fb950",
        "SUCCESS_BG":    "#0f2a1a",
        "WARNING":       "#d29922",
        "WARNING_BG":    "#271f00",
        "ERROR":         "#f85149",
        "ERROR_BG":      "#2d1016",
        "INFO":          "#388bfd",
        "INFO_BG":       "#051d4d",

        # Syntax highlighting
        "SYNTAX_KEYWORD":      "#ff9048",   # keywords → warm orange
        "SYNTAX_TYPE":         "#79c0ff",   # types → blue
        "SYNTAX_STRING":       "#ffbe7a",   # strings → light amber
        "SYNTAX_NUMBER":       "#f0c060",   # numbers → golden
        "SYNTAX_COMMENT":      "#5c5650",   # comments → muted warm
        "SYNTAX_PREPROCESSOR": "#e3a041",   # #include etc → amber
        "SYNTAX_FUNCTION":     "#f4934a",   # function calls → orange
        "SYNTAX_OPERATOR":     "#ff6e30",   # operators → bright orange
    },

    # ── Paper (soft light — the default) ────────────────────────────────
    #
    # Built for long study sessions, not for looking impressive. The rules:
    #
    # * The page is warm off-white, never pure white. Pure white on a bright
    #   screen is the main reason a light theme tires the eyes.
    # * Text is a soft near-black rather than #000. Full contrast against the
    #   background is what makes a page feel heavy.
    # * Borders are barely there. Structure comes from spacing, not from
    #   lines drawn around everything.
    # * The accent is a muted terracotta, not a saturated orange. A colour
    #   that shouts is a colour you stop noticing after an hour.
    "paper": {
        "BASE":          "#f4f1ec",    # warm off-white page
        "SURFACE":       "#faf8f5",    # cards, just above the page
        "SURFACE_ALT":   "#f0ece5",    # inputs, code blocks
        "SURFACE_HOV":   "#eae5dc",    # hover
        "BORDER":        "#e2dcd2",    # barely-there divider
        "BORDER_SUB":    "#ece7de",

        "FOREGROUND":    "#3b3730",    # soft near-black
        "MUTED":         "#7d766b",    # secondary text
        "PLACEHOLDER":   "#aaa398",

        # Accent — muted terracotta
        "ACCENT":        "#b4703a",
        "ACCENT_LIGHT":  "#c98a56",
        "ACCENT_ALT":    "#95582b",
        "ACCENT_TEXT":   "#ffffff",

        "NAV_ACTIVE_BG":     "#efe4d6",
        "NAV_ACTIVE_BG_HOV": "#e7d8c4",
        "LIST_SEL_BG":       "#efe4d6",

        "BTN_DISABLED_BG": "#ebe6dd",
        "BTN_DISABLED_FG": "#ada69b",
        "PRIMARY_HOVER_FG": "#ffffff",

        "CYAN":          "#4d8b98",
        "CYAN_LIGHT":    "#71aab5",

        "SUCCESS":       "#5f8b5c",
        "SUCCESS_BG":    "#e7efe5",
        "WARNING":       "#a3803d",
        "WARNING_BG":    "#f5eede",
        "ERROR":         "#b4605a",
        "ERROR_BG":      "#f6e8e5",
        "INFO":          "#5c7fa5",
        "INFO_BG":       "#e7edf3",

        "SYNTAX_KEYWORD":      "#a3564f",
        "SYNTAX_TYPE":         "#4a6f96",
        "SYNTAX_STRING":       "#6b7d52",
        "SYNTAX_NUMBER":       "#9a6a2e",
        "SYNTAX_COMMENT":      "#a8a196",
        "SYNTAX_PREPROCESSOR": "#9a6a2e",
        "SYNTAX_FUNCTION":     "#7b6191",
        "SYNTAX_OPERATOR":     "#a3564f",
    },

    # ── Dark Purple (legacy, original theme) ────────────────────────────
    "dark_purple": {
        "BASE":          "#0d1117",
        "SURFACE":       "#161b22",
        "SURFACE_ALT":   "#1c2128",
        "SURFACE_HOV":   "#21262d",
        "BORDER":        "#30363d",
        "BORDER_SUB":    "#21262d",

        "FOREGROUND":    "#e6edf3",
        "MUTED":         "#7d8590",
        "PLACEHOLDER":   "#484f58",

        "ACCENT":        "#7c3aed",
        "ACCENT_LIGHT":  "#a78bfa",
        "ACCENT_ALT":    "#4f46e5",
        "ACCENT_TEXT":   "#f5f3ff",

        "NAV_ACTIVE_BG":     "#2d1f5e",
        "NAV_ACTIVE_BG_HOV": "#38276e",
        "LIST_SEL_BG":       "#2d1f5e",

        "BTN_DISABLED_BG": "#3b2f5e",
        "BTN_DISABLED_FG": "#7a6a9c",
        "PRIMARY_HOVER_FG": "#1a0533",

        "CYAN":          "#06b6d4",
        "CYAN_LIGHT":    "#67e8f9",

        "SUCCESS":       "#3fb950",
        "SUCCESS_BG":    "#0f2a1a",
        "WARNING":       "#d29922",
        "WARNING_BG":    "#271f00",
        "ERROR":         "#f85149",
        "ERROR_BG":      "#2d1016",
        "INFO":          "#388bfd",
        "INFO_BG":       "#051d4d",

        "SYNTAX_KEYWORD":      "#ff7b72",
        "SYNTAX_TYPE":         "#79c0ff",
        "SYNTAX_STRING":       "#a5d6ff",
        "SYNTAX_NUMBER":       "#ffa657",
        "SYNTAX_COMMENT":      "#5c6370",
        "SYNTAX_PREPROCESSOR": "#e3b341",
        "SYNTAX_FUNCTION":     "#d2a8ff",
        "SYNTAX_OPERATOR":     "#ff7b72",
    },

    # ── Light / White ────────────────────────────────────────────────────
    "light": {
        "BASE":          "#ffffff",
        "SURFACE":       "#f6f8fa",
        "SURFACE_ALT":   "#eef0f2",
        "SURFACE_HOV":   "#e8eaed",
        "BORDER":        "#d0d7de",
        "BORDER_SUB":    "#e0e4e8",

        "FOREGROUND":    "#1a1a1a",
        "MUTED":         "#6e7781",
        "PLACEHOLDER":   "#adb5bd",

        # Accent — warm orange on white
        "ACCENT":        "#c44f00",
        "ACCENT_LIGHT":  "#e06020",
        "ACCENT_ALT":    "#a33e00",
        "ACCENT_TEXT":   "#ffffff",

        "NAV_ACTIVE_BG":     "#fff0e8",
        "NAV_ACTIVE_BG_HOV": "#ffe0cc",
        "LIST_SEL_BG":       "#fff0e8",

        "BTN_DISABLED_BG": "#f0f0f0",
        "BTN_DISABLED_FG": "#aaaaaa",
        "PRIMARY_HOVER_FG": "#ffffff",

        "CYAN":          "#0891b2",
        "CYAN_LIGHT":    "#06b6d4",

        "SUCCESS":       "#1a7f37",
        "SUCCESS_BG":    "#dafbe1",
        "WARNING":       "#9a6700",
        "WARNING_BG":    "#fff8c5",
        "ERROR":         "#cf222e",
        "ERROR_BG":      "#ffebe9",
        "INFO":          "#0550ae",
        "INFO_BG":       "#ddf4ff",

        "SYNTAX_KEYWORD":      "#cf222e",
        "SYNTAX_TYPE":         "#0550ae",
        "SYNTAX_STRING":       "#0a3069",
        "SYNTAX_NUMBER":       "#953800",
        "SYNTAX_COMMENT":      "#9198a1",
        "SYNTAX_PREPROCESSOR": "#953800",
        "SYNTAX_FUNCTION":     "#8250df",
        "SYNTAX_OPERATOR":     "#cf222e",
    },
}

# ---------------------------------------------------------------------------
# Active theme tokens (module-level, for backwards-compat with all views)
# ---------------------------------------------------------------------------
_ACTIVE_THEME = DEFAULT_THEME
_p = _PALETTES[_ACTIVE_THEME]

# Expose all tokens as module globals so existing code like `theme.ACCENT` works
def _expose(palette: dict[str, str]) -> None:
    import sys
    mod = sys.modules[__name__]
    for key, val in palette.items():
        setattr(mod, key, val)
    # Also expose the syntax constants under old names for code_editor.py
    setattr(mod, "SYNTAX_KEYWORD",      palette["SYNTAX_KEYWORD"])
    setattr(mod, "SYNTAX_TYPE",         palette["SYNTAX_TYPE"])
    setattr(mod, "SYNTAX_STRING",       palette["SYNTAX_STRING"])
    setattr(mod, "SYNTAX_NUMBER",       palette["SYNTAX_NUMBER"])
    setattr(mod, "SYNTAX_COMMENT",      palette["SYNTAX_COMMENT"])
    setattr(mod, "SYNTAX_PREPROCESSOR", palette["SYNTAX_PREPROCESSOR"])
    setattr(mod, "SYNTAX_FUNCTION",     palette["SYNTAX_FUNCTION"])
    setattr(mod, "SYNTAX_OPERATOR",     palette["SYNTAX_OPERATOR"])


_expose(_p)


# ---------------------------------------------------------------------------
# Stylesheet builder — takes a palette dict and returns a full QSS string
# ---------------------------------------------------------------------------

def _build_stylesheet(p: dict[str, str]) -> str:
    return f"""

/* ───────────────────────────────────────────────
   Base reset
──────────────────────────────────────────────── */
QWidget {{
    background-color: {p['BASE']};
    color: {p['FOREGROUND']};
    font-family: -apple-system, "Segoe UI", "Inter", "Ubuntu", sans-serif;
    font-size: 13px;
    selection-background-color: {p['ACCENT']};
    selection-color: {p['ACCENT_TEXT']};
}}

QMainWindow {{
    background-color: {p['BASE']};
}}

QDialog {{
    background-color: {p['SURFACE']};
    border: 1px solid {p['BORDER']};
    border-radius: 12px;
}}

/* ───────────────────────────────────────────────
   Buttons
──────────────────────────────────────────────── */
QPushButton {{
    background-color: {p['SURFACE_ALT']};
    color: {p['FOREGROUND']};
    border: 1px solid {p['BORDER']};
    border-radius: 6px;
    padding: 7px 16px;
    font-size: 13px;
    font-weight: 500;
    outline: none;
}}

QPushButton:hover {{
    background-color: {p['SURFACE_HOV']};
    border-color: {p['MUTED']};
    color: {p['FOREGROUND']};
}}

QPushButton:pressed {{
    background-color: {p['SURFACE']};
    border-color: {p['ACCENT_LIGHT']};
}}

QPushButton:disabled {{
    color: {p['PLACEHOLDER']};
    border-color: {p['BORDER_SUB']};
    background-color: {p['SURFACE']};
}}

/* Primary — orange gradient button */
QPushButton#primary {{
    background-color: {p['ACCENT']};
    color: {p['ACCENT_TEXT']};
    border: none;
    border-radius: 6px;
    font-weight: 600;
    padding: 7px 20px;
}}
QPushButton#primary:hover {{
    background-color: {p['ACCENT_LIGHT']};
    color: {p['PRIMARY_HOVER_FG']};
}}
QPushButton#primary:pressed {{
    background-color: {p['ACCENT_ALT']};
    color: {p['ACCENT_TEXT']};
}}
QPushButton#primary:disabled {{
    background-color: {p['BTN_DISABLED_BG']};
    color: {p['BTN_DISABLED_FG']};
    border: none;
}}

/* Danger */
QPushButton#danger {{
    background-color: transparent;
    border: 1px solid {p['ERROR']};
    color: {p['ERROR']};
    border-radius: 6px;
}}
QPushButton#danger:hover {{
    background-color: {p['ERROR_BG']};
    border-color: #ff4444;
}}

/* Subtle / ghost */
QPushButton#subtle {{
    background-color: transparent;
    border: 1px solid {p['BORDER_SUB']};
    color: {p['MUTED']};
}}
QPushButton#subtle:hover {{
    background-color: {p['SURFACE_ALT']};
    color: {p['FOREGROUND']};
    border-color: {p['BORDER']};
}}

/* Nav buttons in sidebar */
QPushButton#nav_item {{
    background-color: transparent;
    border: none;
    border-radius: 8px;
    padding: 10px 14px;
    text-align: left;
    color: {p['MUTED']};
    font-size: 13px;
    font-weight: 500;
}}
QPushButton#nav_item:hover {{
    background-color: {p['SURFACE_HOV']};
    color: {p['FOREGROUND']};
}}
QPushButton#nav_item_active {{
    background-color: {p['NAV_ACTIVE_BG']};
    border: none;
    border-radius: 8px;
    border-left: 3px solid {p['ACCENT_LIGHT']};
    padding: 10px 14px 10px 11px;
    text-align: left;
    color: {p['ACCENT_LIGHT']};
    font-size: 13px;
    font-weight: 600;
}}
QPushButton#nav_item_active:hover {{
    background-color: {p['NAV_ACTIVE_BG_HOV']};
    color: {p['ACCENT_LIGHT']};
}}

/* ───────────────────────────────────────────────
   Text inputs
──────────────────────────────────────────────── */
QTextEdit, QPlainTextEdit, QLineEdit {{
    background-color: {p['SURFACE']};
    color: {p['FOREGROUND']};
    border: 1px solid {p['BORDER']};
    border-radius: 8px;
    padding: 8px 10px;
    font-size: 13px;
    selection-background-color: {p['ACCENT']};
    selection-color: {p['ACCENT_TEXT']};
}}

QTextEdit:focus, QPlainTextEdit:focus, QLineEdit:focus {{
    border-color: {p['ACCENT']};
    background-color: {p['SURFACE_ALT']};
    outline: none;
}}

QLineEdit::placeholder {{
    color: {p['PLACEHOLDER']};
}}

/* ───────────────────────────────────────────────
   Combo box
──────────────────────────────────────────────── */
QComboBox {{
    background-color: {p['SURFACE_ALT']};
    color: {p['FOREGROUND']};
    border: 1px solid {p['BORDER']};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 13px;
    min-width: 80px;
}}
QComboBox:hover {{
    border-color: {p['MUTED']};
    background-color: {p['SURFACE_HOV']};
}}
QComboBox:focus {{
    border-color: {p['ACCENT']};
}}
QComboBox::drop-down {{
    border: none;
    width: 24px;
}}
QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 5px solid {p['MUTED']};
    width: 0;
    height: 0;
    margin-right: 6px;
}}
QComboBox QAbstractItemView {{
    background-color: {p['SURFACE_ALT']};
    border: 1px solid {p['BORDER']};
    border-radius: 8px;
    color: {p['FOREGROUND']};
    selection-background-color: {p['ACCENT']};
    selection-color: {p['ACCENT_TEXT']};
    padding: 4px;
    outline: none;
}}

/* ───────────────────────────────────────────────
   Spin box
──────────────────────────────────────────────── */
QSpinBox {{
    background-color: {p['SURFACE_ALT']};
    color: {p['FOREGROUND']};
    border: 1px solid {p['BORDER']};
    border-radius: 6px;
    padding: 6px 10px;
}}
QSpinBox:focus {{
    border-color: {p['ACCENT']};
}}
QSpinBox::up-button, QSpinBox::down-button {{
    background-color: {p['SURFACE_HOV']};
    border: none;
    width: 18px;
}}

/* ───────────────────────────────────────────────
   List & Tree Widgets
──────────────────────────────────────────────── */
QListWidget, QTreeWidget {{
    background-color: {p['SURFACE']};
    border: 1px solid {p['BORDER']};
    border-radius: 8px;
    padding: 4px;
    outline: none;
    alternate-background-color: {p['SURFACE_ALT']};
}}

QListWidget::item, QTreeWidget::item {{
    padding: 9px 12px;
    border-radius: 6px;
    margin: 1px 0;
    color: {p['FOREGROUND']};
}}

QListWidget::item:selected, QTreeWidget::item:selected {{
    background-color: {p['LIST_SEL_BG']};
    color: {p['ACCENT_LIGHT']};
}}

QListWidget::item:hover:!selected, QTreeWidget::item:hover:!selected {{
    background-color: {p['SURFACE_HOV']};
}}

/* ───────────────────────────────────────────────
   Group box
──────────────────────────────────────────────── */
QGroupBox {{
    background-color: {p['SURFACE']};
    border: 1px solid {p['BORDER']};
    border-radius: 10px;
    margin-top: 18px;
    padding: 14px 12px 12px 12px;
    font-weight: 600;
    color: {p['FOREGROUND']};
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 12px;
    top: -1px;
    padding: 0 6px;
    background-color: {p['SURFACE']};
    color: {p['MUTED']};
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

/* ───────────────────────────────────────────────
   Tab widget
──────────────────────────────────────────────── */
QTabWidget::pane {{
    border: 1px solid {p['BORDER']};
    border-top: none;
    border-radius: 0 0 10px 10px;
    background-color: {p['SURFACE']};
}}

QTabBar {{
    background-color: {p['SURFACE_ALT']};
}}

QTabBar::tab {{
    background-color: transparent;
    color: {p['MUTED']};
    border: none;
    border-bottom: 2px solid transparent;
    padding: 9px 18px;
    font-size: 13px;
    font-weight: 500;
    margin-right: 2px;
}}

QTabBar::tab:selected {{
    color: {p['ACCENT_LIGHT']};
    border-bottom: 2px solid {p['ACCENT_LIGHT']};
    background-color: transparent;
    font-weight: 600;
}}

QTabBar::tab:hover:!selected {{
    color: {p['FOREGROUND']};
    border-bottom: 2px solid {p['BORDER']};
}}

/* ───────────────────────────────────────────────
   Progress bar
──────────────────────────────────────────────── */
QProgressBar {{
    background-color: {p['SURFACE_ALT']};
    border: none;
    border-radius: 6px;
    height: 10px;
    text-align: center;
    color: transparent;
    font-size: 11px;
}}

QProgressBar::chunk {{
    background-color: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 {p['ACCENT']},
        stop:1 {p['CYAN']}
    );
    border-radius: 6px;
}}

/* ───────────────────────────────────────────────
   Scroll bars
──────────────────────────────────────────────── */
QScrollBar:vertical {{
    background-color: transparent;
    width: 8px;
    margin: 0;
    border: none;
}}
QScrollBar::handle:vertical {{
    background-color: {p['BORDER']};
    border-radius: 4px;
    min-height: 32px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {p['MUTED']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0; width: 0; border: none;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: none;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 8px;
    border: none;
}}
QScrollBar::handle:horizontal {{
    background-color: {p['BORDER']};
    border-radius: 4px;
    min-width: 32px;
}}
QScrollBar::handle:horizontal:hover {{
    background-color: {p['MUTED']};
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    height: 0; width: 0; border: none;
}}

/* ───────────────────────────────────────────────
   Text browser (read-only content)
──────────────────────────────────────────────── */
QTextBrowser {{
    background-color: {p['SURFACE']};
    border: 1px solid {p['BORDER']};
    border-radius: 8px;
    padding: 8px;
    color: {p['FOREGROUND']};
    selection-background-color: {p['ACCENT']};
}}

/* ───────────────────────────────────────────────
   Header view (tables)
──────────────────────────────────────────────── */
QHeaderView::section {{
    background-color: {p['SURFACE_ALT']};
    border: none;
    border-bottom: 1px solid {p['BORDER']};
    padding: 8px 12px;
    color: {p['MUTED']};
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
}}

/* ───────────────────────────────────────────────
   Splitter
──────────────────────────────────────────────── */
QSplitter::handle {{
    background-color: {p['BORDER']};
    margin: 2px;
}}
QSplitter::handle:horizontal {{
    width: 1px;
}}
QSplitter::handle:vertical {{
    height: 1px;
}}

/* ───────────────────────────────────────────────
   Status bar
──────────────────────────────────────────────── */
QStatusBar {{
    background-color: {p['SURFACE_ALT']};
    color: {p['MUTED']};
    border-top: 1px solid {p['BORDER']};
    font-size: 12px;
    padding: 2px 8px;
}}
QStatusBar::item {{
    border: none;
}}

/* ───────────────────────────────────────────────
   Tooltips
──────────────────────────────────────────────── */
QToolTip {{
    background-color: {p['SURFACE_ALT']};
    color: {p['FOREGROUND']};
    border: 1px solid {p['BORDER']};
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 12px;
}}

/* ───────────────────────────────────────────────
   Check box
──────────────────────────────────────────────── */
QCheckBox {{
    color: {p['FOREGROUND']};
    spacing: 8px;
    font-size: 13px;
}}
QCheckBox::indicator {{
    width: 16px;
    height: 16px;
    border: 1px solid {p['BORDER']};
    border-radius: 4px;
    background-color: {p['SURFACE_ALT']};
}}
QCheckBox::indicator:checked {{
    background-color: {p['ACCENT']};
    border-color: {p['ACCENT']};
}}
QCheckBox::indicator:hover {{
    border-color: {p['ACCENT_LIGHT']};
}}

/* ───────────────────────────────────────────────
   Labels — semantic object names
──────────────────────────────────────────────── */
QLabel#title {{
    font-size: 22px;
    font-weight: 700;
    color: {p['FOREGROUND']};
    letter-spacing: -0.3px;
}}
QLabel#subtitle {{
    font-size: 13px;
    color: {p['MUTED']};
}}
QLabel#muted {{
    color: {p['MUTED']};
    font-size: 12px;
}}
QLabel#error {{
    color: {p['ERROR']};
    font-size: 13px;
}}
QLabel#success {{
    color: {p['SUCCESS']};
    font-size: 13px;
}}
QLabel#warning {{
    color: {p['WARNING']};
    font-size: 13px;
}}
QLabel#info {{
    color: {p['INFO']};
    font-size: 13px;
}}
QLabel#brand {{
    font-size: 17px;
    font-weight: 800;
    color: {p['ACCENT_LIGHT']};
    letter-spacing: -0.5px;
}}
QLabel#section_header {{
    font-size: 11px;
    font-weight: 700;
    color: {p['PLACEHOLDER']};
    text-transform: uppercase;
    letter-spacing: 0.8px;
}}
QLabel#badge_success {{
    background-color: {p['SUCCESS_BG']};
    color: {p['SUCCESS']};
    border: 1px solid {p['SUCCESS']};
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel#badge_error {{
    background-color: {p['ERROR_BG']};
    color: {p['ERROR']};
    border: 1px solid {p['ERROR']};
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel#badge_warning {{
    background-color: {p['WARNING_BG']};
    color: {p['WARNING']};
    border: 1px solid {p['WARNING']};
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel#badge_info {{
    background-color: {p['INFO_BG']};
    color: {p['INFO']};
    border: 1px solid {p['INFO']};
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}}
QLabel#badge_muted {{
    background-color: {p['SURFACE_ALT']};
    color: {p['MUTED']};
    border: 1px solid {p['BORDER']};
    border-radius: 10px;
    padding: 2px 8px;
    font-size: 11px;
    font-weight: 600;
}}

/* ───────────────────────────────────────────────
   Dialog buttons
──────────────────────────────────────────────── */
QDialogButtonBox QPushButton {{
    min-width: 80px;
}}

/* ───────────────────────────────────────────────
   Sidebar container
──────────────────────────────────────────────── */
QWidget#sidebar {{
    background-color: {p['SURFACE']};
    border-right: 1px solid {p['BORDER']};
}}

QWidget#content_area {{
    background-color: {p['BASE']};
}}

QWidget#nav_section {{
    background-color: {p['SURFACE']};
}}

/* Lesson card widget */
QFrame#lesson_card {{
    background-color: {p['SURFACE']};
    border: 1px solid {p['BORDER']};
    border-radius: 10px;
}}
QFrame#lesson_card:hover {{
    border-color: {p['ACCENT']};
    background-color: {p['SURFACE_ALT']};
}}
QFrame#lesson_card_done {{
    background-color: {p['SURFACE']};
    border: 1px solid {p['SUCCESS']};
    border-left: 4px solid {p['SUCCESS']};
    border-radius: 10px;
}}
QFrame#lesson_card_done:hover {{
    background-color: {p['SURFACE_ALT']};
}}
QFrame#lesson_card_active {{
    background-color: {p['SURFACE']};
    border: 1px solid {p['ACCENT']};
    border-left: 4px solid {p['ACCENT']};
    border-radius: 10px;
}}

"""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

#: Available theme names and their display labels
THEMES: dict[str, str] = {
    "paper":       "📄  Paper (soft light)",
    "light":       "☀️  Light",
    "dark_orange": "🔥 Dark Orange",
    "dark_purple": "💜 Dark Purple",
}



def get_stylesheet(theme_name: str = DEFAULT_THEME) -> str:
    """Return the full QSS stylesheet for the given theme name."""
    palette = _PALETTES.get(theme_name, _PALETTES[DEFAULT_THEME])
    return _build_stylesheet(palette)


def apply_theme(window: Any, theme_name: str = DEFAULT_THEME) -> None:
    """Apply a theme to the main window and update all module-level token globals."""
    global _ACTIVE_THEME
    _ACTIVE_THEME = theme_name
    palette = _PALETTES.get(theme_name, _PALETTES[DEFAULT_THEME])
    _expose(palette)
    # Rebuild stylesheet with current palette and apply
    window.setStyleSheet(get_stylesheet(theme_name))


def active_theme() -> str:
    """Return the currently active theme name."""
    return _ACTIVE_THEME


# The default stylesheet exposed for backwards compatibility
STYLESHEET = get_stylesheet(DEFAULT_THEME)
