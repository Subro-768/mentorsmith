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

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
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
    QSpinBox,
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
    mark_verified,
    pending_questions,
)
from ..services.exam_prep import ExamPrepService, ExamSession
from . import theme


def _escape(text: str) -> str:
    return html_module.escape(str(text))


def _matches_an_option(answer: str, options: list[str]) -> bool:
    """Whether an answer is one of the options, ignoring case and spacing."""
    wanted = " ".join(answer.lower().split())
    return any(" ".join(option.lower().split()) == wanted for option in options)


class MockDialog(QDialog):
    """Asks for the shape of a practice mock.

    The format is the learner's own, and the dialog says so. The exam's
    real pattern is not offered, because the only pattern the catalogue
    carries is the Cycle Test header - and a CT is not the end-semester
    paper. Inventing an end-semester format on no evidence would be the
    exact thing this module exists to prevent.
    """

    def __init__(self, available: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Practice mock")
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        note = QLabel(
            "A practice format you set, not the exam's official pattern. "
            "The papers you imported do not state an end-semester format, "
            "so this one is yours to choose."
        )
        note.setWordWrap(True)
        note.setObjectName("muted")
        layout.addWidget(note)

        form = QFormLayout()
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, max(1, available))
        self.count_spin.setValue(min(10, max(1, available)))
        form.addRow("Questions", self.count_spin)

        self.minutes_spin = QSpinBox()
        self.minutes_spin.setRange(0, 240)
        self.minutes_spin.setValue(30)
        self.minutes_spin.setSpecialValueText("no time limit")
        form.addRow("Minutes", self.minutes_spin)
        layout.addLayout(form)

        self.source_combo = QComboBox()
        self.source_combo.addItem("Everything in the bank", None)
        self.source_combo.addItem("Past questions only", VERIFIED_PYQ)
        self.source_combo.addItem("Official samples only", OFFICIAL_SAMPLE)
        layout.addWidget(self.source_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def settings(self) -> tuple[int, int, str | None]:
        return (
            self.count_spin.value(),
            self.minutes_spin.value(),
            self.source_combo.currentData(),
        )


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
        #: The review queue and where we are in it.
        self._review_queue: list = []
        self._review_index = 0
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

        # The course record: what the official syllabus actually says.
        self.course_info = QLabel("")
        self.course_info.setObjectName("muted")
        self.course_info.setWordWrap(True)
        self.course_info.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        root.addWidget(self.course_info)

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

        self.mock_button = QPushButton("Timed mock")
        self.mock_button.setObjectName("subtle")
        self.mock_button.setFixedHeight(34)
        self.mock_button.setToolTip(
            "A timed practice run in a format you choose."
        )
        self.mock_button.clicked.connect(self.start_mock)
        buttons.addWidget(self.mock_button)

        self.review_button = QPushButton("Check questions")
        self.review_button.setObjectName("subtle")
        self.review_button.setFixedHeight(34)
        self.review_button.setToolTip(
            "Read a question against your own paper and mark it verified."
        )
        self.review_button.clicked.connect(self.start_review)
        buttons.addWidget(self.review_button)
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

        self.resume_button = QPushButton("Resume")
        self.resume_button.setObjectName("subtle")
        self.resume_button.setFixedHeight(34)
        self.resume_button.setVisible(False)
        self.resume_button.clicked.connect(self.resume_session)
        self.session_bar.addWidget(self.resume_button)
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

        # ── Review panel: the human-check workflow ─────────────────────
        self.review_panel = QWidget()
        review_layout = QVBoxLayout(self.review_panel)
        review_layout.setContentsMargins(0, 0, 0, 0)
        review_layout.setSpacing(8)

        self.review_answer = QLineEdit()
        self.review_answer.setPlaceholderText(
            "The answer from your copy of the paper"
        )
        review_layout.addWidget(self.review_answer)

        self.review_explanation = QLineEdit()
        self.review_explanation.setPlaceholderText(
            "A short explanation (optional)"
        )
        review_layout.addWidget(self.review_explanation)

        self.review_marks = QLineEdit()
        self.review_marks.setPlaceholderText("Marks (optional)")
        self.review_marks.setFixedWidth(120)
        review_layout.addWidget(self.review_marks)

        review_buttons = QHBoxLayout()
        self.review_save = QPushButton("Mark as checked")
        self.review_save.setObjectName("primary")
        self.review_save.setFixedHeight(34)
        self.review_save.clicked.connect(self._on_review_save)
        review_buttons.addWidget(self.review_save)

        self.review_skip = QPushButton("Skip")
        self.review_skip.setObjectName("subtle")
        self.review_skip.setFixedHeight(34)
        self.review_skip.clicked.connect(self._on_review_skip)
        review_buttons.addWidget(self.review_skip)
        review_buttons.addStretch(1)
        review_layout.addLayout(review_buttons)

        self.review_panel.setVisible(False)
        right_layout.addWidget(self.review_panel)

        # The clock. Ticks once a second, and ends the session when the
        # time runs out.
        self.clock = QTimer(self)
        self.clock.setInterval(1000)
        self.clock.timeout.connect(self._on_tick)

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
        self._show_course_info(course)
        self.unit_combo.blockSignals(True)
        self.unit_combo.clear()
        self.unit_combo.addItem("All units", None)
        for unit in course.units if course else []:
            topics = course.topics_in_unit(unit)
            title = ", ".join(t.title for t in topics) if topics else f"Unit {unit}"
            self.unit_combo.addItem(f"Unit {unit} — {title}", unit)
        self.unit_combo.blockSignals(False)
        self.refresh_questions()
        self._offer_resume()

    def _show_course_info(self, course) -> None:
        """Show what the official syllabus says about the course.

        The old course code is shown next to the current one, because the
        papers the learner has carry the old one and a student looking at
        a 2021 paper should be able to see it is the same course.
        """
        if course is None:
            self.course_info.setText("")
            return
        bits = []
        if course.course_code:
            bits.append(f"Course code <b>{course.course_code}</b>")
        if course.previous_course_codes:
            older = ", ".join(course.previous_course_codes)
            bits.append(f"earlier code {older}")
        if course.regulation:
            bits.append(course.regulation)
        if course.academic_council:
            bits.append(f"approved {course.academic_council}")
        if course.category or course.credits is not None:
            detail = " · ".join(
                part for part in (
                    course.category,
                    f"{course.credits} credits" if course.credits else "",
                    f"L{course.lecture_hours} T{course.tutorial_hours} "
                    f"P{course.practical_hours}" if course.lecture_hours else "",
                ) if part
            )
            bits.append(detail)
        if course.sessions_per_unit:
            bits.append(f"{course.sessions_per_unit} sessions per unit")
        if course.exam_pattern:
            bits.append(f"Assessment: {course.exam_pattern}")
        self.course_info.setText("  ·  ".join(bits))

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
    # ------------------------------------------------------------------
    # The timed mock
    # ------------------------------------------------------------------
    def start_mock(self) -> None:
        """Ask for the format, then run it."""
        available = len(self.service.questions(self.course_id))
        if not available:
            QMessageBox.information(
                self, "Nothing to mock",
                "There are no questions in this course yet.",
            )
            return
        dialog = MockDialog(available, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        count, minutes, source = dialog.settings()
        try:
            self.session = self.service.start_mock(
                self.course_id, count=count, minutes=minutes, source_type=source
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Cannot start", str(exc))
            return
        self._leave_review_mode()
        self.service.save_session(self.session)
        self.clock.start()
        self._show_current()

    def resume_session(self) -> None:
        """Pick up an unfinished session."""
        session = self.service.open_session(self.course_id)
        if session is None:
            self.resume_button.setVisible(False)
            return
        self.session = session
        self._leave_review_mode()
        if session.timed:
            self.clock.start()
        self._show_current()

    def _offer_resume(self) -> None:
        """Show the resume button when there is something to resume."""
        session = self.service.open_session(self.course_id)
        if session is None:
            self.resume_button.setVisible(False)
            return
        self.resume_button.setVisible(True)
        self.resume_button.setToolTip(
            f'Continue "{session.title}" — question '
            f"{session.index + 1} of {len(session.questions)}"
        )

    def _on_tick(self) -> None:
        """Once a second: update the clock, and end the session on time."""
        if self.session is None or not self.session.timed:
            self.clock.stop()
            return
        left = self.service.seconds_left(self.session)
        minutes, seconds = divmod(left, 60)
        self.session_label.setText(
            f"{self.session.title} — question {self.session.index + 1} of "
            f"{len(self.session.questions)}  ·  {minutes:02d}:{seconds:02d} left"
        )
        if left <= 0:
            self.clock.stop()
            self.service.close_session(self.session)
            self._show_results()

    def _leave_review_mode(self) -> None:
        """Put the practice controls back and hide the review ones."""
        self.review_panel.setVisible(False)
        self.choice_box.setVisible(True)
        self.submit_button.setVisible(True)
        self.next_button.setVisible(True)

    def start_practice(self) -> None:
        """Start a session over the questions the filters selected."""
        self._leave_review_mode()
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
        self._leave_review_mode()
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

    # ------------------------------------------------------------------
    # The human-check workflow
    # ------------------------------------------------------------------
    def start_review(self) -> None:
        """Open the review queue: questions waiting for a human check."""
        self._review_queue = list(pending_questions(self.course_id))
        self._review_index = 0
        self.review_panel.setVisible(True)
        self.choice_box.setVisible(False)
        self.submit_button.setVisible(False)
        self.next_button.setVisible(False)
        if not self._review_queue:
            self.session_label.setText("Nothing waiting for a check")
            self.body.setHtml(
                "<p><b>Every question in this course has been checked.</b></p>"
                "<p>Nothing is waiting for a human to compare it against the "
                "paper.</p>"
            )
            return
        self._show_next_for_review()

    def _show_next_for_review(self) -> None:
        if self._review_index >= len(self._review_queue):
            self.session_label.setText("Review finished")
            self.review_panel.setVisible(False)
            self.submit_button.setVisible(True)
            self.next_button.setVisible(True)
            self.refresh_questions()
            self.body.setHtml(
                "<p><b>That is the lot.</b></p>"
                "<p>Every question you have looked at is now marked as "
                "checked. The ones you skipped are still waiting.</p>"
            )
            return

        question = self._review_queue[self._review_index]
        self.session_label.setText(
            f"Checking question {self._review_index + 1} of "
            f"{len(self._review_queue)}"
        )
        self.review_answer.setText(question.answer)
        self.review_explanation.setText(question.explanation)
        self.review_marks.setText(str(question.marks or ""))
        self.body.setHtml(
            f"<div style='font-family:system-ui,sans-serif;font-size:13px;"
            f"color:{theme.FOREGROUND};line-height:1.6'>"
            f"<p style='color:{theme.WARNING};font-weight:700;'>"
            f"Extracted from your paper - not yet checked.</p>"
            f"<p style='font-size:15px;font-weight:600'>"
            f"{_escape(question.question_text)}</p>"
            f"<p style='color:{theme.MUTED}'>Options as extracted:</p>"
            + "".join(
                f"<p style='margin:2px 0'>{chr(ord('a') + i)}. "
                f"{_escape(option)}</p>"
                for i, option in enumerate(question.options)
            )
            + f"<hr style='border-color:{theme.BORDER}'>"
            f"<p style='color:{theme.MUTED};font-size:11px'>"
            f"Source: {_escape(question.source_reference)}</p>"
            f"<p style='color:{theme.MUTED};font-size:11px'>"
            f"Check it against that page, then type the answer if the paper "
            f"gives one. Marking it checked records that you did.</p>"
            f"</div>"
        )

    def _on_review_save(self) -> None:
        """Record the answer and mark the question as checked."""
        question = self._review_queue[self._review_index]
        marks = self.review_marks.text().strip()
        marks_value = int(marks) if marks.isdigit() else None
        answer = self.review_answer.text().strip()
        if answer and question.options and not _matches_an_option(answer, question.options):
            # Say so rather than storing it silently. It usually means the
            # *extraction* of the options is wrong - two columns read as
            # one, or a line lost - and the question cannot be graded until
            # that is put right.
            QMessageBox.warning(
                self, "Answer not among the options",
                "That answer is not one of the options as they were "
                "extracted.\n\n"
                "That usually means the options were read wrongly rather "
                "than that the answer is wrong. The question has still been "
                "marked as checked, but it cannot be graded automatically "
                "until the options are put right.",
            )

        updated = mark_verified(
            question.id,
            answer=answer,
            explanation=self.review_explanation.text(),
            marks=marks_value,
        )
        if updated is None:
            QMessageBox.warning(
                self, "Could not save",
                "That question is no longer in the bank.",
            )
            return
        self._review_index += 1
        self._show_next_for_review()

    def _on_review_skip(self) -> None:
        self._review_index += 1
        self._show_next_for_review()

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
