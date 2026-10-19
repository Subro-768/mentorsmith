"""The Exam Prep screen.

A student comes here to practise against their own papers. Two things this
screen is careful about:

**What a question is.** Every question carries a label saying what it is -
a verified past question, a sample question, something the project wrote,
or a predicted one - and a second label saying whether a human has checked
it yet. An unverified extraction says so, in those words, right next to the
question. A student must never have to guess whether they are looking at
a real paper.

**Whether an answer was graded.** The papers do not print an answer key, so
most questions cannot be marked automatically. When that happens the screen
says *ungraded*, tells the student which page of which paper to check, and
records the attempt without counting it as a mistake. A session that
graded nothing reports no accuracy, rather than 0%.

The screen is a normal part of the app: a course selector, a filterable
list of questions, a practice session, and a results page.
"""

from __future__ import annotations

import html as html_module

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QScrollArea,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..core.exam import (
    OFFICIAL_SAMPLE,
    ORIGINAL_PRACTICE,
    PENDING_REVIEW,
    PREDICTED_PRACTICE,
    VERIFIED,
    VERIFIED_PYQ,
)
from ..services.exam_prep import ExamPrepService, ExamSession
from . import theme


def _escape(text: str) -> str:
    return html_module.escape(str(text))


class ExamPrepView(QWidget):
    """Course selection, a filterable bank, a session and the results."""

    #: Emitted when the student asks to open a lesson.
    open_lesson_requested = pyqtSignal(str)

    def __init__(self, database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = ExamPrepService(database)
        self.course_id = ""
        self.session: ExamSession | None = None
        self._question_ids: list[str] = []
        self._build_ui()
        self.reload_courses()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 16)
        root.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Exam Prep")
        title.setObjectName("title")
        header.addWidget(title)

        self.course_combo = QComboBox()
        self.course_combo.setFixedWidth(320)
        self.course_combo.currentIndexChanged.connect(self._on_course_changed)
        header.addWidget(self.course_combo)
        header.addStretch(1)

        self.import_hint = QLabel("")
        self.import_hint.setObjectName("muted")
        header.addWidget(self.import_hint)
        root.addLayout(header)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setHandleWidth(1)

        # ── Left: filters and the question list ───────────────────────
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 12, 0)
        left_layout.setSpacing(8)

        filters = QGroupBox("Filters")
        filters_layout = QVBoxLayout(filters)
        filters_layout.setSpacing(6)

        self.unit_combo = QComboBox()
        self.unit_combo.currentIndexChanged.connect(self.refresh_questions)
        filters_layout.addWidget(self.unit_combo)

        self.source_combo = QComboBox()
        self.source_combo.addItem("All sources", "")
        self.source_combo.addItem("Past question (paper)", VERIFIED_PYQ)
        self.source_combo.addItem("Official sample", OFFICIAL_SAMPLE)
        self.source_combo.addItem("Original practice", ORIGINAL_PRACTICE)
        self.source_combo.addItem("Predicted practice", PREDICTED_PRACTICE)
        self.source_combo.currentIndexChanged.connect(self.refresh_questions)
        filters_layout.addWidget(self.source_combo)

        self.status_combo = QComboBox()
        self.status_combo.addItem("Any verification status", "")
        self.status_combo.addItem("Verified by a human", VERIFIED)
        self.status_combo.addItem("Pending human review", PENDING_REVIEW)
        self.status_combo.currentIndexChanged.connect(self.refresh_questions)
        filters_layout.addWidget(self.status_combo)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search questions...")
        self.search_input.textChanged.connect(self.refresh_questions)
        filters_layout.addWidget(self.search_input)

        left_layout.addWidget(filters)

        self.bank_summary = QLabel("")
        self.bank_summary.setObjectName("muted")
        self.bank_summary.setWordWrap(True)
        left_layout.addWidget(self.bank_summary)

        self.question_list = QListWidget()
        self.question_list.setObjectName("chapter_list")
        self.question_list.setWordWrap(True)
        self.question_list.currentRowChanged.connect(self._on_question_selected)
        left_layout.addWidget(self.question_list, 1)

        buttons = QHBoxLayout()
        self.practise_button = QPushButton("Practise these")
        self.practise_button.setObjectName("primary")
        self.practise_button.setFixedHeight(34)
        self.practise_button.clicked.connect(self.start_practice)
        buttons.addWidget(self.practise_button)

        self.mistakes_button = QPushButton("Practise my mistakes")
        self.mistakes_button.setObjectName("subtle")
        self.mistakes_button.setFixedHeight(34)
        self.mistakes_button.setToolTip(
            "Only the questions that were graded and answered wrongly."
        )
        self.mistakes_button.clicked.connect(self.start_mistakes)
        buttons.addWidget(self.mistakes_button)
        buttons.addStretch(1)
        left_layout.addLayout(buttons)

        splitter.addWidget(left)

        # ── Right: the question, the session, the results ─────────────
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(12, 0, 0, 0)
        right_layout.setSpacing(10)

        self.session_bar = QHBoxLayout()
        self.session_label = QLabel("")
        self.session_label.setObjectName("subtitle")
        self.session_bar.addWidget(self.session_label)
        self.session_bar.addStretch(1)

        self.next_button = QPushButton("Next →")
        self.next_button.setObjectName("primary")
        self.next_button.setFixedHeight(34)
        self.next_button.clicked.connect(self._on_next)
        self.session_bar.addWidget(self.next_button)
        right_layout.addLayout(self.session_bar)

        self.body = QTextBrowser()
        self.body.setOpenExternalLinks(False)
        self.body.setStyleSheet(
            f"QTextBrowser {{ background-color: {theme.SURFACE}; "
            f"border: 1px solid {theme.BORDER}; border-radius: 10px; padding: 16px; }}"
        )
        right_layout.addWidget(self.body, 1)

        self.choice_box = QGroupBox("Your answer")
        self.choice_layout = QVBoxLayout(self.choice_box)
        self.choice_buttons: list[QRadioButton] = []
        right_layout.addWidget(self.choice_box)

        self.submit_button = QPushButton("Submit answer")
        self.submit_button.setObjectName("primary")
        self.submit_button.setFixedHeight(36)
        self.submit_button.clicked.connect(self._on_submit)
        right_layout.addWidget(self.submit_button)

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        splitter.setSizes([420, 700])

        root.addWidget(splitter, 1)

    # ------------------------------------------------------------------
    # Content
    # ------------------------------------------------------------------
    def reload_courses(self) -> None:
        """Load the course catalogue into the selector."""
        self.course_combo.blockSignals(True)
        self.course_combo.clear()
        for course in self.service.courses():
            label = course.title
            if course.course_code:
                label = f"{course.course_code} — {course.title}"
            # The verification state travels with the name. A course
            # nobody has checked against official material says so here,
            # rather than looking the same as one that has.
            if course.verification_status == PENDING_REVIEW:
                label += "  (catalogue not yet verified)"
            self.course_combo.addItem(label, course.id)
        self.course_combo.blockSignals(False)
        if self.course_combo.count():
            self.course_combo.setCurrentIndex(0)
            self._on_course_changed()
        else:
            self._show_empty()

    def _on_course_changed(self) -> None:
        self.course_id = self.course_combo.currentData() or ""
        if not self.course_id:
            self._show_empty()
            return
        course = self.service.course(self.course_id)
        self.unit_combo.blockSignals(True)
        self.unit_combo.clear()
        self.unit_combo.addItem("All units", None)
        for unit in course.units if course else []:
            topics = course.topics_in_unit(unit)
            title = ", ".join(t.title for t in topics) if topics else f"Unit {unit}"
            self.unit_combo.addItem(f"Unit {unit} — {title}", unit)
        self.unit_combo.blockSignals(False)
        self.refresh_questions()

    def _show_empty(self) -> None:
        """An empty state, not a fabricated course."""
        self.bank_summary.setText(
            "No course is installed. Import your own papers with:\n\n"
            "    python3 tools/import_exam_papers.py --folder <your papers>"
        )
        self.question_list.clear()
        self.body.setHtml(
            "<p><b>No exam-prep content yet.</b></p>"
            "<p>MentorSmith ships the <i>course catalogue</i> but not the "
            "questions: past papers and question banks are your own material, "
            "and they are not ours to redistribute.</p>"
            "<p>Point the importer at a folder of your papers and it will "
            "extract the questions into your own copy of the app, each one "
            "marked <i>pending human review</i> until you have checked it "
            "against the paper:</p>"
            "<p><code>python3 tools/import_exam_papers.py --folder "
            "&lt;your papers&gt;</code></p>"
        )

    def refresh_questions(self) -> None:
        """Reload the question list for the current filters."""
        if not self.course_id:
            return
        unit = self.unit_combo.currentData()
        questions = self.service.questions(
            self.course_id,
            unit=unit if unit is not None else None,
            source_type=self.source_combo.currentData() or None,
            verification_status=self.status_combo.currentData() or None,
            search=self.search_input.text(),
        )
        counts = self.service.counts(self.course_id)
        pending = counts["by_status"].get(PENDING_REVIEW, 0)
        self.bank_summary.setText(
            f"{len(questions)} of {counts['total']} question(s) shown. "
            f"{pending} awaiting a human check — none of them is a "
            f"“verified past question” yet."
        )

        self.question_list.clear()
        self._question_ids = []
        for question in questions:
            item = QListWidgetItem(self._item_text(question))
            item.setToolTip(question.source_reference)
            self.question_list.addItem(item)
            self._question_ids.append(question.id)
        if questions:
            self.question_list.setCurrentRow(0)

    def _item_text(self, question) -> str:
        mark = "✓" if question.verification_status == VERIFIED else "○"
        return f"{mark} Q{question.source_question_number}  {question.question_text[:70]}"

    def _on_question_selected(self, row: int) -> None:
        """Show a question in the right-hand pane, without starting a session."""
        if row < 0 or row >= len(self._question_ids):
            return
        question = self._question(self._question_ids[row])
        if question is None:
            return
        self._render_question(question, show_options=False)

    def _question(self, question_id: str):
        for question in self.service.questions(self.course_id):
            if question.id == question_id:
                return question
        return None

    # ------------------------------------------------------------------
    # Rendering
    # ------------------------------------------------------------------
    def _clear_choices(self) -> None:
        while self.choice_layout.count():
            item = self.choice_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.choice_buttons = []

    def _render_question(self, question, *, show_options: bool) -> None:
        """Show a question, its label and its source."""
        self._clear_choices()
        options = list(question.options)
        if show_options:
            options_html = "".join(
                f"<p style='margin:2px 0'>{chr(ord('a') + i)}. "
                f"{_escape(option)}</p>"
                for i, option in enumerate(options)
            )
        else:
            options_html = (
                f"<p style='color:{theme.MUTED}'>"
                f"Open a practice session to answer this.</p>"
            )
        badge = self._badge_html(question)
        self.body.setHtml(
            f"<div style='font-family:system-ui,sans-serif;font-size:13px;"
            f"color:{theme.FOREGROUND};line-height:1.6'>"
            f"{badge}"
            f"<p style='font-size:15px;font-weight:600'>"
            f"{_escape(question.question_text)}</p>"
            f"{options_html}"
            f"<hr style='border-color:{theme.BORDER}'>"
            f"<p style='color:{theme.MUTED};font-size:11px'>"
            f"Source: {_escape(question.source_reference)}</p>"
            f"</div>"
        )

        if show_options:
            for option in options:
                button = QRadioButton(option)
                self.choice_layout.addWidget(button)
                self.choice_buttons.append(button)
        self.choice_box.setVisible(show_options)

    def _badge_html(self, question) -> str:
        label = question.display_label
        colour = {
            VERIFIED_PYQ: theme.ACCENT,
            OFFICIAL_SAMPLE: theme.INFO,
            ORIGINAL_PRACTICE: theme.SUCCESS,
            PREDICTED_PRACTICE: theme.WARNING,
        }.get(question.source_type, theme.MUTED)
        extra = ""
        if question.verification_status == PENDING_REVIEW:
            extra = (
                f"<br><span style='color:{theme.WARNING};font-size:11px'>"
                f"Not yet checked against the paper.</span>"
            )
        return (
            f"<span style='color:{colour};font-weight:700;font-size:11px'>"
            f"{_escape(label)}</span>{extra}"
        )

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------
    def start_practice(self) -> None:
        """Start a session over the questions the filters selected."""
        questions = self.service.questions(
            self.course_id,
            unit=self.unit_combo.currentData(),
            source_type=self.source_combo.currentData() or None,
            verification_status=self.status_combo.currentData() or None,
            search=self.search_input.text(),
        )
        if not questions:
            QMessageBox.information(
                self, "Nothing to practise",
                "No questions match the current filters.",
            )
            return
        self.session = self.service.start_session(questions, self.course_id)
        self._show_current()

    def start_mistakes(self) -> None:
        """Start a session over the questions actually got wrong."""
        questions = self.service.mistake_questions(self.course_id)
        if not questions:
            QMessageBox.information(
                self, "No mistakes yet",
                "Nothing here has been graded and answered wrongly yet.\n\n"
                "A question only becomes a mistake once it has an answer key "
                "to be graded against - most papers do not print one.",
            )
            return
        self.session = self.service.start_session(
            questions, self.course_id, "My mistakes"
        )
        self._show_current()

    def _show_current(self) -> None:
        if self.session is None:
            return
        question = self.session.current
        if question is None:
            self._show_results()
            return
        position = self.session.index + 1
        self.session_label.setText(
            f"{self.session.title} — question {position} of "
            f"{len(self.session.questions)}"
        )
        self.submit_button.setText("Submit answer")
        self.next_button.setEnabled(False)
        self._render_question(question, show_options=True)

    def _on_submit(self) -> None:
        """Record the chosen answer."""
        if self.session is None:
            return
        chosen = ""
        for button in self.choice_buttons:
            if button.isChecked():
                chosen = button.text()
                break
        result = self.service.submit(self.session, chosen)
        self._render_feedback(result)

    def _render_feedback(self, result) -> None:
        """Say what happened, honestly."""
        if result.status == "correct":
            verdict = (
                f"<span style='color:{theme.SUCCESS};font-weight:700'>"
                f"Correct.</span>"
            )
        elif result.status == "wrong":
            verdict = (
                f"<span style='color:{theme.ERROR};font-weight:700'>"
                f"Not quite.</span> The answer is "
                f"<b>{_escape(result.question.answer)}</b>."
            )
        else:
            verdict = (
                f"<span style='color:{theme.WARNING};font-weight:700'>"
                f"Answer recorded, not graded.</span> This paper does not "
                f"print an answer key, so there is nothing to check it "
                f"against here."
            )

        pointer = ""
        if result.needs_paper_check:
            pointer = (
                f"<p style='color:{theme.MUTED};font-size:11px'>"
                f"Check it on: {_escape(result.paper_pointer)}</p>"
            )

        explanation = ""
        if result.explanation:
            explanation = (
                f"<p>{_escape(result.explanation)}</p>"
            )

        self.body.setHtml(
            f"<div style='font-family:system-ui,sans-serif;font-size:13px;"
            f"color:{theme.FOREGROUND};line-height:1.6'>"
            f"{verdict}{pointer}{explanation}"
            f"<hr style='border-color:{theme.BORDER}'>"
            f"<p style='color:{theme.MUTED};font-size:11px'>"
            f"You chose: {_escape(result.chosen) or '(skipped)'}</p>"
            f"</div>"
        )
        self._clear_choices()
        self.next_button.setEnabled(True)
        self.submit_button.setEnabled(False)

    def _on_next(self) -> None:
        if self.session is None:
            return
        if self.session.finished:
            self._show_results()
            return
        self.submit_button.setEnabled(True)
        self._show_current()

    def _show_results(self) -> None:
        if self.session is None:
            return
        results = self.service.finish(self.session)
        accuracy = results.accuracy
        accuracy_text = (
            f"{round(accuracy * 100)}% of the graded questions were right."
            if accuracy is not None
            else (
                "No question in this session could be graded — the papers do "
                "not print answer keys — so there is no score to report."
            )
        )
        lines = [
            f"<p style='font-size:15px;font-weight:600'>{_escape(results.title)}</p>",
            f"<p>{_escape(results.summary())}</p>",
            f"<p>{accuracy_text}</p>",
        ]
        if results.weak_units():
            weak = ", ".join(
                f"Unit {unit} ({round(score * 100)}%)"
                for unit, score in results.weak_units()
            )
            lines.append(f"<p><b>Worth revisiting:</b> {_escape(weak)}</p>")
        if results.unmeasured_units():
            unmeasured = ", ".join(str(u) for u in results.unmeasured_units())
            lines.append(
                f"<p style='color:{theme.MUTED}'>Units {unmeasured} were "
                f"attempted but not graded, so they are unmeasured rather "
                f"than weak.</p>"
            )
        if results.mistakes:
            lines.append(
                f"<p><b>{len(results.mistakes)} mistake(s)</b> — these are "
                f"the questions worth doing again.</p>"
            )
        if results.ungraded_results:
            lines.append(
                f"<p style='color:{theme.MUTED}'>{len(results.ungraded_results)} "
                f"question(s) had no answer key, so they are not counted as "
                f"mistakes.</p>"
            )
        # Refresh the list *before* writing the results, not after:
        # refreshing selects the first row, and the selection handler
        # replaces the body - which would wipe the results page the moment
        # it was shown.
        self.refresh_questions()

        self.body.setHtml(
            f"<div style='font-family:system-ui,sans-serif;font-size:13px;"
            f"color:{theme.FOREGROUND};line-height:1.6'>" + "".join(lines) + "</div>"
        )
        self.session_label.setText("Session finished")
        self.submit_button.setEnabled(False)
        self.next_button.setEnabled(False)
        self._clear_choices()
