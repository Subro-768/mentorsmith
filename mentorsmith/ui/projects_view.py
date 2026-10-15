"""The Projects screen: propose, start, and work through milestones.

Milestones are deliberately small and each one carries acceptance criteria the
learner can check themselves. Hints are available but recorded, and the screen
asks whether work was independent — because that distinction is what the
project history is actually for.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from ..core.concepts import ConceptModel
from ..core.db import Database
from ..core.mastery import MasteryAssessment
from ..core.projects import milestone_progress, propose_projects, save_project
from . import theme
from .code_editor import MarkdownView


class ProjectsView(QWidget):
    """Browse proposed projects and work through their milestones."""

    data_changed = pyqtSignal()

    def __init__(
        self,
        database: Database,
        model: ConceptModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.database = database
        self.model = model
        self._proposals = []
        self._current_project_id: str | None = None
        self._build_ui()

    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(8)

        title = QLabel("Projects")
        title.setObjectName("title")
        root.addWidget(title)

        intro = QLabel(
            "Projects are suggested from concepts you have demonstrated, not "
            "merely opened. Each one is split into small milestones with "
            "acceptance criteria you can check yourself."
        )
        intro.setObjectName("subtitle")
        intro.setWordWrap(True)
        root.addWidget(intro)

        progress_row = QHBoxLayout()
        progress_row.addWidget(QLabel("Milestones:"))
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        progress_row.addWidget(self.progress_bar, 1)
        self.progress_label = QLabel()
        self.progress_label.setObjectName("muted")
        progress_row.addWidget(self.progress_label)
        root.addLayout(progress_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.addWidget(QLabel("Suggested projects"))
        self.project_list = QListWidget()
        self.project_list.setWordWrap(True)
        self.project_list.itemClicked.connect(self._on_project_clicked)
        left_layout.addWidget(self.project_list, 1)

        self.actions = QHBoxLayout()
        self.start_button = QPushButton("Start this project")
        self.actions.addWidget(self.start_button)
        left_layout.addLayout(self.actions)
        splitter.addWidget(left)

        self.detail_view = MarkdownView()
        self.detail_view.setPlaceholderText("Select a project to see its details.")
        splitter.addWidget(self.detail_view)

        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        root.addWidget(splitter, 1)

        # Milestone controls
        controls = QHBoxLayout()
        self.status_combo = QLabel()
        controls.addWidget(self.status_combo)
        controls.addStretch(1)
        self.note_button = QPushButton("Record notes")
        self.help_check = QCheckBox("This milestone needed substantial help")
        controls.addWidget(self.help_check)
        self.status_button = QPushButton("Set status")
        controls.addWidget(self.status_button)
        root.addLayout(controls)

        self.milestone_view = QTextBrowser()
        self.milestone_view.setMaximumHeight(220)
        root.addWidget(self.milestone_view)

        self._selected_milestone_id: int | None = None
        self.status_button.clicked.connect(self._on_set_status)
        self.note_button.clicked.connect(self._on_record_notes)
        self.start_button.clicked.connect(self._on_start)

    # ------------------------------------------------------------------
    def refresh(self, assessments: dict[str, MasteryAssessment]) -> None:
        """Repropose projects from current evidence."""
        self._proposals = propose_projects(self.model, assessments, limit=5)
        self.project_list.clear()
        for proposal in self._proposals:
            started = self.database.get_project(proposal.project.id) is not None
            flag = "READY" if proposal.ready else "blocked"
            mark = "[started]" if started else ""
            item = QListWidgetItem(
                f"{proposal.project.title} ({flag}) {mark}\n"
                f"{proposal.estimated_difficulty} · "
                f"{len(proposal.project.milestones)} milestones"
            )
            item.setData(Qt.ItemDataRole.UserRole, proposal.project.id)
            item.setToolTip(proposal.rationale)
            self.project_list.addItem(item)
        if self.project_list.count():
            self.project_list.setCurrentRow(0)
            self._show_proposal(self.project_list.item(0))
        self._refresh_progress()

    def _refresh_progress(self) -> None:
        done = total = 0
        for project in self.database.list_projects():
            milestones = self.database.milestones_for(str(project["id"]))
            total += len(milestones)
            done += sum(1 for m in milestones if m.get("status") == "done")
        self.progress_bar.setValue(int(round(done * 100 / total)) if total else 0)
        self.progress_label.setText(f"{done} of {total} milestones complete")

    def _on_project_clicked(self, item: QListWidgetItem) -> None:
        self._show_proposal(item)

    def _show_proposal(self, item: QListWidgetItem) -> None:
        project_id = str(item.data(Qt.ItemDataRole.UserRole))
        proposal = next(
            (p for p in self._proposals if p.project.id == project_id), None
        )
        if proposal is None:
            return
        self._current_project_id = project_id

        status_colour = theme.SUCCESS if proposal.ready else theme.WARNING
        html = [
            f"<h2>{_escape(proposal.project.title)}</h2>",
            f"<p>{_escape(proposal.project.purpose)}</p>",
            f"<p>Estimated difficulty: <b>{proposal.estimated_difficulty}</b> "
            f"(catalogue: {proposal.project.difficulty})</p>",
            f"<p style='color:{status_colour}'>{_escape(proposal.rationale)}</p>",
            "<h3>Concepts involved</h3><ul>",
        ]
        for concept_id in proposal.project.concepts:
            concept = self.model.get(concept_id)
            html.append(f"<li>{_escape(concept.title if concept else concept_id)}</li>")
        html.append("</ul>")

        if proposal.missing_prerequisites:
            html.append("<h3>Prerequisites to strengthen first</h3><ul>")
            for concept_id in proposal.missing_prerequisites:
                concept = self.model.get(concept_id)
                html.append(
                    f"<li>{_escape(concept.title if concept else concept_id)}</li>"
                )
            html.append("</ul>")

        html.append("<h3>Milestones</h3>")
        for index, milestone in enumerate(proposal.project.milestones, start=1):
            html.append(
                f"<p><b>{index}. {_escape(milestone.title)}</b><br>"
                f"{_escape(milestone.requirements)}</p>"
            )
            html.append("<ul>")
            for criterion in milestone.acceptance_criteria:
                html.append(f"<li>{_escape(criterion)}</li>")
            html.append("</ul>")

        if proposal.project.extensions:
            html.append("<h3>Extension challenges</h3><ul>")
            for extension in proposal.project.extensions:
                html.append(f"<li>{_escape(extension)}</li>")
            html.append("</ul>")

        self.detail_view.setHtml("".join(html))
        self.start_button.setEnabled(True)
        self._render_milestones(project_id)

    def _render_milestones(self, project_id: str) -> None:
        """Show stored milestone state for a started project."""
        if self.database.get_project(project_id) is None:
            self.milestone_view.setHtml(
                "<p style='color:"
                + theme.MUTED
                + "'>Start the project to track milestones.</p>"
            )
            self.status_combo.setText("Not started")
            return

        milestones = self.database.milestones_for(project_id)
        progress = milestone_progress(milestones)
        self.status_combo.setText(
            f"Project progress: {progress['done']}/{progress['total']} milestones"
        )

        rows = []
        for milestone in milestones:
            criteria = str(milestone.get("acceptance_criteria", "")).split(",")
            rows.append(
                f"<p><b>{milestone['ordinal']}. {_escape(str(milestone['title']))}</b> "
                f"— <span style='color:{_status_colour(str(milestone['status']))}'>"
                f"{_escape(str(milestone['status']))}</span></p>"
                f"<p>{_escape(str(milestone['requirements']))}</p><ul>"
                + "".join(f"<li>{_escape(c)}</li>" for c in criteria if c)
                + "</ul>"
            )
        activity = self.database.project_activity_for(project_id)
        if activity:
            rows.append("<h4>Recorded notes</h4><ul>")
            for entry in activity[:10]:
                helped = " (needed substantial help)" if entry["needed_substantial_help"] else ""
                rows.append(
                    f"<li>{_escape(str(entry['created_at']))} — "
                    f"{_escape(str(entry['notes']))}{helped}</li>"
                )
            rows.append("</ul>")

        self.milestone_view.setHtml("".join(rows))
        self._refresh_progress()

    # ------------------------------------------------------------------
    def _on_start(self) -> None:
        if not self._current_project_id:
            return
        proposal = next(
            (p for p in self._proposals if p.project.id == self._current_project_id),
            None,
        )
        if proposal is None:
            return
        if not proposal.ready:
            answer = QMessageBox.question(
                self,
                "Start anyway?",
                "This project is not ready for you yet:\n\n"
                f"{proposal.rationale}\n\n"
                "You can still start it, but you will probably get stuck.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return

        save_project(self.database, proposal)
        self.database.set_project_status(proposal.project.id, "in_progress")
        self.database.record_activity(
            "project_started", None, f"{proposal.project.title} started"
        )
        self._render_milestones(proposal.project.id)
        self.data_changed.emit()

    def _on_set_status(self) -> None:
        """Advance a milestone, recording whether help was needed."""
        if not self._current_project_id:
            return
        milestones = self.database.milestones_for(self._current_project_id)
        pending = [m for m in milestones if m.get("status") != "done"]
        if not pending:
            QMessageBox.information(
                self, "All done", "Every milestone in this project is complete."
            )
            return

        milestone = pending[0]
        self._selected_milestone_id = int(milestone["id"])
        options = ["in_progress", "done", "blocked", "pending"]
        choice, accepted = QInputDialog.getItem(
            self,
            f"Milestone {milestone['ordinal']}: {milestone['title']}",
            "Set status to:",
            options,
            0,
            False,
        )
        if not accepted:
            return

        self.database.set_milestone_status(self._selected_milestone_id, choice)
        self.database.record_project_activity(
            self._current_project_id,
            f"Milestone {milestone['ordinal']} set to {choice}",
            milestone_id=self._selected_milestone_id,
            needed_substantial_help=self.help_check.isChecked(),
        )

        remaining = [m for m in self.database.milestones_for(self._current_project_id)
                     if m.get("status") != "done"]
        if choice == "done" and not remaining:
            self.database.set_project_status(self._current_project_id, "done")
        else:
            self.database.set_project_status(self._current_project_id, "in_progress")

        self.help_check.setChecked(False)
        self._render_milestones(self._current_project_id)
        self.data_changed.emit()

    def _on_record_notes(self) -> None:
        if not self._current_project_id:
            return
        note, accepted = QInputDialog.getMultiLineText(
            self,
            "Record notes",
            "What did you build, what went wrong, and what did you work out?\n"
            "Notes are kept so you can read them back later.",
        )
        if not accepted or not note.strip():
            return
        self.database.record_project_activity(
            self._current_project_id,
            note.strip(),
            needed_substantial_help=self.help_check.isChecked(),
        )
        self.help_check.setChecked(False)
        self._render_milestones(self._current_project_id)
        self.data_changed.emit()


def _status_colour(status: str) -> str:
    return {
        "done": theme.SUCCESS,
        "in_progress": theme.INFO,
        "blocked": theme.ERROR,
        "pending": theme.MUTED,
    }.get(status, theme.MUTED)


def _escape(text: str) -> str:
    import html as html_module

    return html_module.escape(str(text or ""))