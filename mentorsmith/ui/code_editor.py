"""Code editor with C++ syntax highlighting and a line-number gutter.

Built on ``QPlainTextEdit`` rather than ``QTextEdit``: it handles very large
documents efficiently and supports undo/redo cleanly. Highlighting is done
with ``QSyntaxHighlighter``, which is part of PyQt6, so there is no third-party
editor dependency.
"""

from __future__ import annotations

import re

from PyQt6.QtCore import QRect, QSize, Qt, pyqtSignal
from PyQt6.QtGui import (
    QColor,
    QFont,
    QFontDatabase,
    QPainter,
    QPalette,
    QSyntaxHighlighter,
    QTextCharFormat,
    QTextCursor,
)
from PyQt6.QtWidgets import QPlainTextEdit, QTextBrowser, QTextEdit, QWidget

from . import theme

# Order matters: strings and comments are matched before operators so that
# punctuation inside them is not mistaken for code.
RULES: list[tuple[str, str, object]] = [
    # Preprocessor directives: #include <iostream>
    (r"^[ \t]*\#[a-zA-Z_]+", "preprocessor", None),
    # Preprocessor continuation inside an #include line
    (r"<[A-Za-z0-9_./+]+>", "include", theme.SYNTAX_STRING),
    # Block comments
    (r"/\*", "comment", None),
    (r"\*/", "comment_end", None),
    # Line comments
    (r"//.*", "comment", None),
    # Strings
    (r'"(?:\\.|[^"\\])*"', "string", None),
    (r"'(?:\\.|[^'\\])'", "string", None),
    # Numbers
    (r"\b\d[\d']*(?:\.\d[\d']*)?(?:[eE][+-]?\d+)?[uUlLfF]*\b", "number", None),
    (r"\b0[xX][0-9a-fA-F']+\b", "number", None),
    # Keywords
    (
        r"\b(?:alignas|alignof|and|asm|auto|bool|break|case|catch|char|class|"
        r"const|consteval|constexpr|constinit|const_cast|continue|co_await|"
        r"co_return|co_yield|decltype|default|delete|do|double|dynamic_cast|"
        r"else|enum|explicit|export|extern|false|float|for|friend|goto|if|"
        r"inline|int|long|mutable|namespace|new|noexcept|not|nullptr|operator|"
        r"or|private|protected|public|register|reinterpret_cast|requires|"
        r"return|short|signed|sizeof|static|static_assert|static_cast|struct|"
        r"switch|template|this|thread_local|throw|true|try|typedef|typeid|"
        r"typename|union|unsigned|using|virtual|void|volatile|while|wchar_t)\b",
        "keyword",
        theme.SYNTAX_KEYWORD,
    ),
    # Standard library types worth highlighting
    (
        r"\b(?:std|string|vector|map|set|pair|unique_ptr|shared_ptr|size_t|"
        r"int32_t|uint32_t|int64_t|double|int|char|bool|long|short|float|"
        r"unsigned|auto|const|namespace)\b",
        "type",
        theme.SYNTAX_TYPE,
    ),
    # Common standard library names
    (
        r"\b(?:std::)?(?:cout|cin|endl|printf|scanf|malloc|free|sizeof|"
        r"push_back|emplace_back|begin|end|size|length|make_unique|make_shared|"
        r"atoi|stoi|sqrt|abs|fabs)\b",
        "function",
        theme.SYNTAX_FUNCTION,
    ),
    (r"::", "operator", theme.SYNTAX_OPERATOR),
    (r"\b(?:std::)\b", "namespace", theme.SYNTAX_PREPROCESSOR),
    # Common operators
    (
        r"[+\-*/%=<>!&|^~?:]+",
        "operator",
        theme.SYNTAX_OPERATOR,
    ),
]


class CppHighlighter(QSyntaxHighlighter):
    """Applies the theme's syntax colours to C++ source."""

    def __init__(self, document=None) -> None:
        super().__init__(document)
        self._rules: list[tuple[re.Pattern[str], QTextCharFormat]] = []
        self._comment_format = QTextCharFormat()
        self._comment_format.setForeground(QColor(theme.SYNTAX_COMMENT))
        self._comment_format.setFontItalic(True)
        self._in_comment = False

        for pattern, kind, colour in RULES:
            fmt = QTextCharFormat()
            if kind == "comment":
                fmt = self._comment_format
            elif kind == "comment_end":
                fmt = self._comment_format
            elif colour:
                fmt.setForeground(QColor(str(colour)))
            self._rules.append((re.compile(pattern), fmt))

    def highlightBlock(self, text: str | None) -> None:  # noqa: N802 - Qt API
        if not text:
            return

        # Propagate an open block comment into the following lines.
        previous_state = self.previousBlockState()
        self._in_comment = previous_state == 1

        start = 0
        if self._in_comment:
            end = text.find("*/")
            if end == -1:
                self.setFormat(0, len(text), self._comment_format)
                self.setCurrentBlockState(1)
                return
            self.setFormat(0, end + 2, self._comment_format)
            start = end + 2
            self._in_comment = False

        for pattern, fmt in self._rules:
            for match in pattern.finditer(text, start):
                if match.start() < start:
                    continue
                self.setFormat(match.start(), match.end() - match.start(), fmt)
                if pattern.pattern == r"/\*":
                    # Everything after an unterminated /* is a comment.
                    rest = match.end()
                    if rest >= len(text):
                        self.setFormat(match.start(), len(text) - match.start(), self._comment_format)
                        self.setCurrentBlockState(1)
                        self._in_comment = True
                        return
                    end = text.find("*/", rest)
                    if end == -1:
                        self.setFormat(match.start(), len(text) - match.start(), self._comment_format)
                        self.setCurrentBlockState(1)
                        self._in_comment = True
                        return
                    self.setFormat(match.start(), end + 2 - match.start(), self._comment_format)

        self.setCurrentBlockState(1 if self._in_comment else 0)


class LineNumberGutter(QWidget):
    """Narrow widget drawn in the editor's left margin showing line numbers."""

    def __init__(self, editor: "CodeEditor") -> None:
        super().__init__(editor)
        self.editor = editor

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt API
        return QSize(self.editor.line_number_width(), 0)

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.editor.paint_line_numbers(event)


class CodeEditor(QPlainTextEdit):
    """A read-write C++ editor with line numbers and highlighting."""

    #: Emitted with the current text whenever it changes.
    text_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._highlighter = CppHighlighter(self.document())
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        self.setTabStopDistance(4 * self.fontMetrics().horizontalAdvance(" "))

        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSize(11)
        self.setFont(font)

        palette = self.palette()
        palette.setColor(QPalette.ColorRole.Base, QColor(theme.SURFACE))
        palette.setColor(QPalette.ColorRole.Text, QColor(theme.FOREGROUND))
        palette.setColor(
            QPalette.ColorRole.Highlight, QColor(theme.ACCENT)
        )
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#101010"))
        self.setPalette(palette)

        self._gutter = LineNumberGutter(self)
        self.blockCountChanged.connect(self._update_gutter_width)
        self.updateRequest.connect(self._update_gutter)
        self.cursorPositionChanged.connect(self._highlight_current_line)
        self._update_gutter_width(0)
        self._highlight_current_line()

        self.textChanged.connect(lambda: self.text_changed.emit(self.toPlainText()))

    # ------------------------------------------------------------------
    # Gutter plumbing
    # ------------------------------------------------------------------
    def _update_gutter_width(self, _count: int) -> None:
        self.setViewportMargins(self.line_number_width(), 0, 0, 0)

    def _update_gutter(self, rect: QRect, dy: int) -> None:
        if dy:
            self._gutter.scroll(0, dy)
        else:
            self._gutter.update(0, rect.y(), self._gutter.width(), rect.height())
        if rect.contains(self.viewport().rect()):
            self._update_gutter_width(0)

    def line_number_width(self) -> int:
        """Width needed for the widest line number currently displayed."""
        digits = max(2, len(str(max(1, self.blockCount()))))
        return 12 + self.fontMetrics().horizontalAdvance("9") * digits

    def resizeEvent(self, event) -> None:  # noqa: N802 - Qt API
        super().resizeEvent(event)
        rect = self.contentsRect()
        self._gutter.setGeometry(
            QRect(rect.left(), rect.top(), self.line_number_width(), rect.height())
        )

    def paint_line_numbers(self, event) -> None:
        """Draw the numbers for the currently visible blocks."""
        painter = QPainter(self._gutter)
        painter.fillRect(event.rect(), QColor(theme.SURFACE_ALT))
        painter.setPen(QColor(theme.MUTED))

        block = self.firstVisibleBlock()
        block_number = block.blockNumber()
        top = self.blockBoundingGeometry(block).translated(self.contentOffset()).top()
        bottom = top + self.blockBoundingRect(block).height()

        current = self.textCursor().blockNumber()
        while block.isValid() and top <= event.rect().bottom():
            if block.isVisible() and bottom >= event.rect().top():
                painter.setPen(
                    QColor(theme.ACCENT) if block_number == current else QColor(theme.MUTED)
                )
                painter.drawText(
                    0,
                    int(top),
                    self._gutter.width() - 6,
                    self.fontMetrics().height(),
                    Qt.AlignmentFlag.AlignRight,
                    str(block_number + 1),
                )
            block = block.next()
            top = bottom
            bottom = top + self.blockBoundingRect(block).height()
            block_number += 1

    def _highlight_current_line(self) -> None:
        """Add a subtle band on the cursor's line.

        Uses an extra selection rather than an ``ExtraSelection`` format so the
        highlight survives the syntax highlighter reformatting the block.
        """
        selection = QTextEdit.ExtraSelection()
        colour = QColor(theme.SURFACE_ALT)
        selection.format.setBackground(colour)
        selection.format.setProperty(QTextCharFormat.Property.FullWidthSelection, True)
        selection.cursor = self.textCursor()
        selection.cursor.clearSelection()
        self.setExtraSelections([selection])

    # ------------------------------------------------------------------
    # Convenience
    # ------------------------------------------------------------------
    def code(self) -> str:
        return self.toPlainText()

    def set_code(self, text: str) -> None:
        self.setPlainText(text)


class MarkdownView(QTextBrowser):
    """Read-only pane that renders the lesson Markdown.

    The small converter below handles the subset the lessons use: headings,
    bullet lists, fenced code blocks, inline code and bold. It is deliberately
    minimal — pulling in a full Markdown library for this would not earn its
    keep.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setOpenExternalLinks(False)

    def set_markdown(self, text: str) -> None:
        self.setHtml(self.markdown_to_html(text))


def markdown_to_html(text: str) -> str:
    """Convert the lesson Markdown subset to HTML for display."""
    import html as html_module

    lines = text.splitlines()
    out: list[str] = []
    in_code = False
    code_buffer: list[str] = []

    def flush_code() -> None:
        if not code_buffer:
            return
        body = html_module.escape("\n".join(code_buffer))
        out.append(f'<pre style="background:{theme.SURFACE};padding:8px;'
                   f'border:1px solid {theme.BORDER};border-radius:4px;'
                   f'color:{theme.SYNTAX_STRING};">{body}</pre>')
        code_buffer.clear()

    def inline(value: str) -> str:
        escaped = html_module.escape(value)
        # Inline code first, so its contents are not further transformed.
        escaped = re.sub(
            r"`([^`]+)`",
            lambda m: (
                f'<code style="background:{theme.SURFACE_ALT};padding:1px 4px;'
                f'color:{theme.SYNTAX_STRING};">{m.group(1)}</code>'
            ),
            escaped,
        )
        escaped = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", escaped)
        escaped = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<i>\1</i>", escaped)
        return escaped

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code:
                flush_code()
            in_code = not in_code
            continue
        if in_code:
            code_buffer.append(line)
            continue

        if not stripped:
            continue

        if stripped.startswith("###"):
            out.append(f"<h3>{inline(stripped.lstrip('#').strip())}</h3>")
        elif stripped.startswith("##"):
            out.append(f"<h2>{inline(stripped.lstrip('#').strip())}</h2>")
        elif stripped.startswith("#"):
            out.append(f"<h1>{inline(stripped.lstrip('#').strip())}</h1>")
        elif stripped.startswith(("- ", "* ")):
            out.append(f"<li>{inline(stripped[2:])}</li>")
        elif stripped[:3].isdigit() and stripped[3:4] == ".":
            out.append(f"<li>{inline(stripped[4:].strip())}</li>")
        elif stripped.startswith("|") and set(stripped) <= set("|- "):
            continue  # markdown table rule
        elif stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            out.append(
                "<tr>"
                + "".join(f"<td style='padding:3px 8px'>{inline(c)}</td>" for c in cells)
                + "</tr>"
            )
        else:
            out.append(f"<p>{inline(stripped)}</p>")

    flush_code()

    # Wrap loose runs of list items so they render as lists.
    html_text = "\n".join(out)
    html_text = re.sub(r"((?:<li>.*?</li>\n?)+)", r"<ul>\1</ul>", html_text)
    return html_text


def select_all(editor: QPlainTextEdit) -> None:
    """Select the whole editor contents (used by the Ctrl+A shortcut path)."""
    cursor = editor.textCursor()
    cursor.select(QTextCursor.SelectionType.Document)
    editor.setTextCursor(cursor)