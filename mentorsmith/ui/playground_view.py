"""Interactive Code Playground View.

Allows learners to write, run, and experiment with free-form code across all 5
languages (C++, Python, Java, C, and JavaScript) with stdin support, presets,
and immediate execution feedback.
"""

from __future__ import annotations

import time
from pathlib import Path
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..config import work_dir as default_work_dir
from ..core import curriculum_registry
from ..execution import adapter as execution_adapter
from . import theme
from .code_editor import CodeEditor


def _escape(text: str) -> str:
    """HTML-escape program output and compiler diagnostics.

    These strings come from a compiler or from the learner's own program,
    so both can contain <, > and &. Putting them into the output pane
    unescaped would let a program inject markup into the UI.
    """
    import html as html_module

    return html_module.escape(text or "")

_TEMPLATES: dict[str, dict[str, str]] = {
    "cpp": {
        "Hello World": '#include <iostream>\n\nint main() {\n    std::cout << "Hello, MentorSmith Playground! 🚀\\n";\n    return 0;\n}\n',
        "Data Structure (Vector)": '#include <iostream>\n#include <vector>\n#include <numeric>\n\nint main() {\n    std::vector<int> nums = {10, 20, 30, 40, 50};\n    int sum = std::accumulate(nums.begin(), nums.end(), 0);\n    std::cout << "Sum: " << sum << "\\n";\n    return 0;\n}\n',
        "Pointers & Memory": '#include <iostream>\n\nint main() {\n    int val = 42;\n    int* ptr = &val;\n    std::cout << "Value: " << val << " at address: " << ptr << "\\n";\n    *ptr = 100;\n    std::cout << "Updated Value: " << val << "\\n";\n    return 0;\n}\n',
    },
    "python": {
        "Hello World": 'def main():\n    print("Hello from Python Playground! 🐍")\n\nif __name__ == "__main__":\n    main()\n',
        "List Comprehensions & Dictionaries": 'squares = [x**2 for x in range(1, 11)]\nfreq = {x: x % 3 for x in squares}\nprint("Squares:", squares)\nprint("Modulo Frequencies:", freq)\n',
        "Object-Oriented Design": 'class Robot:\n    def __init__(self, name: str, battery: int = 100):\n        self.name = name\n        self.battery = battery\n\n    def status(self) -> str:\n        return f"Robot {self.name} has {self.battery}% power remaining."\n\nbot = Robot("CyberBunny")\nprint(bot.status())\n',
    },
    "java": {
        "Hello World": 'public class Main {\n    public static void main(String[] args) {\n        System.out.println("Hello, Java Playground! ☕");\n    }\n}\n',
        "Collections & Streams": 'import java.util.ArrayList;\nimport java.util.List;\n\npublic class Main {\n    public static void main(String[] args) {\n        List<String> items = new ArrayList<>();\n        items.add("Algorithms");\n        items.add("Concurrency");\n        items.add("Memory Systems");\n        items.forEach(item -> System.out.println("• " + item));\n    }\n}\n',
        "Classes & Encapsulation": 'public class Main {\n    static class Counter {\n        private int count = 0;\n        public void increment() { count++; }\n        public int getCount() { return count; }\n    }\n\n    public static void main(String[] args) {\n        Counter c = new Counter();\n        c.increment();\n        c.increment();\n        System.out.println("Count: " + c.getCount());\n    }\n}\n',
    },
    "c": {
        "Hello World": '#include <stdio.h>\n\nint main(void) {\n    printf("Hello from C Systems Playground! ⚙️\\n");\n    return 0;\n}\n',
        "Dynamic Allocation (malloc)": '#include <stdio.h>\n#include <stdlib.h>\n\nint main(void) {\n    int n = 5;\n    int *arr = (int *)malloc(n * sizeof(int));\n    if (!arr) return 1;\n    for (int i = 0; i < n; i++) arr[i] = (i + 1) * 10;\n    for (int i = 0; i < n; i++) printf("%d ", arr[i]);\n    printf("\\n");\n    free(arr);\n    return 0;\n}\n',
        "Structures & Pointers": '#include <stdio.h>\n\ntypedef struct {\n    int x, y;\n} Point;\n\nvoid move(Point *p, int dx, int dy) {\n    p->x += dx;\n    p->y += dy;\n}\n\nint main(void) {\n    Point pt = {10, 20};\n    move(&pt, 5, -5);\n    printf("Point is now at (%d, %d)\\n", pt.x, pt.y);\n    return 0;\n}\n',
    },
    "javascript": {
        "Hello World": 'console.log("Hello from JavaScript Playground! 🌐");\n',
        "Asynchronous Promises": 'async function fetchSimulation() {\n    const delay = ms => new Promise(res => setTimeout(res, ms));\n    console.log("Fetching simulated payload...");\n    await delay(100);\n    console.log("Payload received: { status: 200, data: [1, 2, 3] }");\n}\nfetchSimulation();\n',
        "Event Emitter & Closures": 'function createStore(initial) {\n    let val = initial;\n    return {\n        get: () => val,\n        set: (next) => { val = next; console.log("State updated:", val); }\n    };\n}\nconst store = createStore(42);\nstore.set(100);\n',
    },
}


class PlaygroundView(QWidget):
    """Full-featured code playground for unconstrained scratchpad development."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.language: str = "cpp"
        self._build_ui()
        self.set_language("cpp")

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # ── Top bar: Header & Controls ────────────────────────────────────
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        title = QLabel("Code Playground ⚡")
        title.setObjectName("title")
        title_col.addWidget(title)

        subtitle = QLabel("Unconstrained scratchpad to experiment with algorithms, patterns, and language features.")
        subtitle.setObjectName("subtitle")
        title_col.addWidget(subtitle)
        header_row.addLayout(title_col)
        header_row.addStretch(1)

        # Language dropdown
        lang_lbl = QLabel("Language:")
        lang_lbl.setStyleSheet(f"color: {theme.MUTED}; font-weight: 600;")
        header_row.addWidget(lang_lbl)

        self.lang_combo = QComboBox()
        self.lang_combo.setFixedHeight(34)
        for lid in curriculum_registry.LANGUAGE_IDS:
            self.lang_combo.addItem(curriculum_registry.display_name(lid), lid)
        self.lang_combo.currentIndexChanged.connect(self._on_lang_combo_changed)
        header_row.addWidget(self.lang_combo)

        # Preset templates dropdown
        template_lbl = QLabel("Template:")
        template_lbl.setStyleSheet(f"color: {theme.MUTED}; font-weight: 600;")
        header_row.addWidget(template_lbl)

        self.template_combo = QComboBox()
        self.template_combo.setFixedHeight(34)
        self.template_combo.currentIndexChanged.connect(self._on_template_selected)
        header_row.addWidget(self.template_combo)

        # Run Button
        self.run_btn = QPushButton("▶  Run Code")
        self.run_btn.setObjectName("primary")
        self.run_btn.setFixedHeight(34)
        self.run_btn.clicked.connect(self.run_code)
        header_row.addWidget(self.run_btn)

        root.addLayout(header_row)

        # ── Main Splitter: Code Editor | Stdin & Output Terminal ──────────
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(2)

        # Left: Editor pane
        editor_box = QWidget()
        editor_lay = QVBoxLayout(editor_box)
        editor_lay.setContentsMargins(0, 0, 8, 0)
        editor_lay.setSpacing(6)

        editor_lbl = QLabel("Source Code:")
        editor_lbl.setStyleSheet(f"font-weight: 600; color: {theme.FOREGROUND};")
        editor_lay.addWidget(editor_lbl)

        self.editor = CodeEditor()
        editor_lay.addWidget(self.editor, 1)
        splitter.addWidget(editor_box)

        # Right: Terminal & Stdin pane
        term_box = QWidget()
        term_lay = QVBoxLayout(term_box)
        term_lay.setContentsMargins(8, 0, 0, 0)
        term_lay.setSpacing(8)

        # Stdin input
        stdin_row = QHBoxLayout()
        stdin_lbl = QLabel("Standard Input (stdin):")
        stdin_lbl.setStyleSheet(f"font-weight: 600; color: {theme.MUTED};")
        stdin_row.addWidget(stdin_lbl)
        stdin_row.addStretch(1)
        term_lay.addLayout(stdin_row)

        self.stdin_input = QPlainTextEdit()
        self.stdin_input.setPlaceholderText("Enter interactive input here before running...")
        self.stdin_input.setFixedHeight(70)
        self.stdin_input.setStyleSheet(
            f"QPlainTextEdit {{ background-color: {theme.SURFACE}; border: 1px solid {theme.BORDER}; "
            f"border-radius: 8px; font-family: monospace; font-size: 12px; color: {theme.FOREGROUND}; padding: 6px; }}"
        )
        term_lay.addWidget(self.stdin_input)

        # Execution Output
        out_row = QHBoxLayout()
        out_lbl = QLabel("Output Terminal:")
        out_lbl.setStyleSheet(f"font-weight: 600; color: {theme.FOREGROUND};")
        out_row.addWidget(out_lbl)
        out_row.addStretch(1)

        self.status_chip = QLabel("Ready")
        self.status_chip.setObjectName("badge_muted")
        out_row.addWidget(self.status_chip)
        term_lay.addLayout(out_row)

        self.output_view = QTextBrowser()
        self.output_view.setStyleSheet(
            f"QTextBrowser {{ background-color: {theme.BASE}; border: 1px solid {theme.BORDER}; "
            f"border-radius: 8px; font-family: 'JetBrains Mono', 'Fira Code', 'Courier New', monospace; "
            f"font-size: 12px; color: {theme.FOREGROUND}; padding: 12px; }}"
        )
        term_lay.addWidget(self.output_view, 1)

        splitter.addWidget(term_box)
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([650, 450])

        root.addWidget(splitter, 1)

    def set_language(self, language: str) -> None:
        self.language = language
        idx = self.lang_combo.findData(language)
        if idx >= 0 and self.lang_combo.currentIndex() != idx:
            self.lang_combo.setCurrentIndex(idx)

        # Update templates combo
        self.template_combo.blockSignals(True)
        self.template_combo.clear()
        templates = _TEMPLATES.get(language, {})
        for name in templates:
            self.template_combo.addItem(name)
        self.template_combo.blockSignals(False)

        # Load first template by default
        if templates:
            first_name = list(templates.keys())[0]
            self.editor.set_code(templates[first_name])

    def _on_lang_combo_changed(self, index: int) -> None:
        lang = self.lang_combo.currentData()
        if lang:
            self.set_language(lang)

    def _on_template_selected(self, index: int) -> None:
        name = self.template_combo.currentText()
        templates = _TEMPLATES.get(self.language, {})
        if name in templates:
            self.editor.set_code(templates[name])

    def run_code(self) -> None:
        code = self.editor.code()
        stdin = self.stdin_input.toPlainText()
        self.status_chip.setText("⏳ Running...")
        self.status_chip.setObjectName("badge_info")
        self.status_chip.style().unpolish(self.status_chip)
        self.status_chip.style().polish(self.status_chip)

        adapter = execution_adapter(
            self.language,
            default_work_dir() / "playground" / self.language,
            sandbox=False,
        )
        adapter.compile_timeout = 30
        adapter.run_timeout = 10

        t0 = time.time()
        # The execution adapters expose run(), which returns
        # (build_result, run_result) - not a combined run_code(). run_result is
        # None when the build failed, which is how a compile error is told from
        # a runtime one.
        try:
            build_result, run_result = adapter.run(code, stdin_data=stdin)
        except Exception as error:   # includes ToolMissingError
            self.status_chip.setText("\u2716 Cannot run")
            self.status_chip.setObjectName("badge_error")
            self.status_chip.style().unpolish(self.status_chip)
            self.status_chip.style().polish(self.status_chip)
            self.output_view.setHtml(
                "<pre style='margin:0; font-family:monospace;'>"
                f"<span style='color:{theme.ERROR};'>{_escape(str(error))}</span>"
                "</pre>"
            )
            return
        elapsed = round(time.time() - t0, 3)

        out_lines: list[str] = []
        if not build_result.ok:
            # Nothing ran. Show the compiler's own words, unmodified.
            self.status_chip.setText("\u2716 Compile Error")
            self.status_chip.setObjectName("badge_error")
            out_lines.append(
                f"<span style='color:{theme.ERROR};'><b>Compilation failed:</b></span><br>"
            )
            detail = build_result.stderr or build_result.error or "(no diagnostics)"
            out_lines.append(
                f"<span style='color:{theme.WARNING};'>{_escape(detail)}</span>"
            )
        elif run_result is None:
            self.status_chip.setText("\u2716 Did not run")
            self.status_chip.setObjectName("badge_error")
            out_lines.append(
                f"<span style='color:{theme.ERROR};'>{_escape(build_result.error)}</span>"
            )
        elif run_result.ok:
            self.status_chip.setText(f"\u2713 Success ({elapsed}s)")
            self.status_chip.setObjectName("badge_success")
            if run_result.stdout:
                out_lines.append(
                    f"<span style='color:{theme.FOREGROUND};'>"
                    f"{_escape(run_result.stdout)}</span>"
                )
            else:
                out_lines.append(
                    f"<span style='color:{theme.MUTED};'>[finished with exit code "
                    f"{run_result.exit_code} - no stdout]</span>"
                )
            if run_result.stderr.strip():
                out_lines.append(
                    f"<span style='color:{theme.WARNING};'>"
                    f"{_escape(run_result.stderr)}</span>"
                )
        else:
            # Ran, and failed. A timeout is called out separately from an
            # ordinary non-zero exit, because they mean different things.
            timed_out = getattr(run_result, "timed_out", False)
            self.status_chip.setText(
                f"\u26a0 {'Timed out' if timed_out else 'Runtime Error'} ({elapsed}s)"
            )
            self.status_chip.setObjectName("badge_error")
            out_lines.append(
                f"<span style='color:{theme.ERROR};'><b>"
                f"{'Timed out' if timed_out else 'Runtime error'}:</b> exit code "
                f"{run_result.exit_code}</span><br>"
            )
            if run_result.stderr:
                out_lines.append(
                    f"<span style='color:{theme.ERROR};'>"
                    f"{_escape(run_result.stderr)}</span>"
                )
            if run_result.stdout:
                out_lines.append(
                    f"<br><span style='color:{theme.FOREGROUND};'>"
                    f"{_escape(run_result.stdout)}</span>"
                )

        self.status_chip.style().unpolish(self.status_chip)
        self.status_chip.style().polish(self.status_chip)
        self.output_view.setHtml(
            "<pre style='margin:0; font-family:monospace;'>"
            + "".join(out_lines)
            + "</pre>"
        )
