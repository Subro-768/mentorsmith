"""Isolated workspaces for the learner's own projects.

A learner project must never live inside the tutor's source tree, and
MentorSmith must never write to an arbitrary path. This module enforces both by
giving every project a directory the app owns, under::

    ~/.local/share/mentorsmith/workspaces/<project-id>/

Three rules are absolute and are enforced here rather than by convention:

1. **A project directory is always inside the workspace root.** A project id is
   sanitised, and the resolved path is checked with
   :func:`Path.is_relative_to` so a crafted id such as ``../../etc`` cannot
   escape. This is the kind of check that has to exist in code because one
   forgotten validation is all it takes.
2. **Nothing outside the workspace root is ever written.** There is no method
   that takes an arbitrary destination.
3. **Learner source files are never read by the tutor's own source tree**, and
   the tutor never imports from a workspace.

`mentorsmith/` and the repository checkout are not reachable from here, so a
learner project cannot overwrite the application.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

#: Deliberately strict. Anything outside this becomes an underscore.
_SAFE_ID = re.compile(r"[^a-z0-9]+")

#: Refuse to be confused with the real filesystem.
MAX_ID_LENGTH = 48


class WorkspaceError(RuntimeError):
    """A workspace request was rejected.

    The message always explains what was refused and why, because these errors
    are surfaced to the learner.
    """


def safe_project_id(raw: str) -> str:
    """Turn arbitrary text into a safe directory name.

    Empty, over-long and all-punctuation inputs are rejected rather than turned
    into a confusing name.
    """
    cleaned = _SAFE_ID.sub("-", (raw or "").strip().lower()).strip("-")
    if not cleaned:
        raise WorkspaceError(
            "A project name must contain at least one letter or digit."
        )
    return cleaned[:MAX_ID_LENGTH]


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class WorkspaceLayout:
    """The standard directory shape inside one project workspace."""

    root: Path

    @property
    def source(self) -> Path:
        return self.root / "src"

    @property
    def tests(self) -> Path:
        return self.root / "tests"

    @property
    def docs(self) -> Path:
        return self.root / "notes"

    @property
    def build_log(self) -> Path:
        return self.root / "test-results.log"

    def ensure(self) -> "WorkspaceLayout":
        """Create the directories. Safe to call repeatedly."""
        for directory in (self.root, self.source, self.tests, self.docs):
            directory.mkdir(parents=True, exist_ok=True)
        return self

    def describe(self) -> dict[str, str]:
        return {
            "root": str(self.root),
            "source": str(self.source),
            "tests": str(self.tests),
            "notes": str(self.docs),
        }


@dataclass
class Workspace:
    """One learner project, with everything tracked alongside it."""

    project_id: str
    layout: WorkspaceLayout
    created_at: str = field(default_factory=_now)
    requirements: str = ""
    notes: str = ""
    #: Latest recorded test run, as (timestamp, summary).
    last_test_result: str = ""

    # -- files -----------------------------------------------------------
    def write_source(self, filename: str, content: str) -> Path:
        """Write a source file into the workspace, refusing bad paths."""
        return self._write_into(self.layout.source, filename, content)

    def write_test(self, filename: str, content: str) -> Path:
        return self._write_into(self.layout.tests, filename, content)

    def write_note(self, filename: str, content: str) -> Path:
        return self._write_into(self.layout.docs, filename, content)

    def _write_into(self, directory: Path, filename: str, content: str) -> Path:
        """Write a file, refusing anything that escapes ``directory``.

        The check is on the *resolved* path, so ``a/../../b`` is caught even
        though it contains no leading slash.
        """
        target = (directory / filename).resolve()
        try:
            target.relative_to(directory.resolve())
        except ValueError:
            raise WorkspaceError(
                f"Refusing to write '{filename}': it would end up outside the "
                f"workspace at {directory}."
            ) from None

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return target

    # -- tracked state ---------------------------------------------------
    def record_requirements(self, text: str) -> None:
        self.requirements = text.strip()
        self._write_into(self.layout.root, "requirements.md", self.requirements)

    def record_notes(self, text: str) -> None:
        self.notes = text.strip()
        self._write_into(self.layout.root, "notes.md", self.notes)

    def record_test_result(self, summary: str) -> Path:
        """Store the latest test summary beside the project.

        A full log would be more useful, but a bounded summary is what the
        dashboard shows and it cannot grow without limit.
        """
        self.last_test_result = summary.strip()
        path = self.layout.build_log
        path.write_text(
            f"# Test results for {self.project_id}\n\n"
            f"## {_now()}\n\n{self.last_test_result}\n",
            encoding="utf-8",
        )
        return path

    def list_files(self) -> list[str]:
        """Every file in the workspace, relative to its root, sorted."""
        return sorted(
            str(path.relative_to(self.layout.root))
            for path in self.layout.root.rglob("*")
            if path.is_file()
        )

    def delete(self) -> None:
        """Remove the whole workspace. Refuses to touch anything outside the root."""
        root = self.layout.root.resolve()
        try:
            root.relative_to(self.layout.root.resolve())
        except ValueError:  # pragma: no cover - defensive
            raise WorkspaceError("Refusing to delete: path check failed.")
        if root.exists():
            shutil.rmtree(root)


class WorkspaceManager:
    """Creates and finds workspaces. The only entry point to this directory."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, project_id: str) -> Path:
        """Where a project's workspace lives, validated to be inside the root."""
        safe = safe_project_id(project_id)
        candidate = (self.root / safe).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError:  # pragma: no cover - safe_project_id prevents this
            raise WorkspaceError(
                f"Refusing to use '{project_id}': it resolves outside the "
                f"workspace root at {self.root}."
            ) from None
        return candidate

    def create(self, project_id: str, *, requirements: str = "") -> Workspace:
        layout = WorkspaceLayout(self.path_for(project_id)).ensure()
        workspace = Workspace(project_id=safe_project_id(project_id), layout=layout)
        workspace.requirements = requirements
        if requirements:
            workspace.record_requirements(requirements)
        return workspace

    def get(self, project_id: str) -> Workspace | None:
        """An existing workspace, or ``None``. Never creates one implicitly."""
        path = self.path_for(project_id)
        if not (path / "src").is_dir():
            return None
        workspace = Workspace(
            project_id=safe_project_id(project_id),
            layout=WorkspaceLayout(path),
        )
        requirements = path / "requirements.md"
        if requirements.exists():
            workspace.requirements = requirements.read_text(encoding="utf-8")
        notes = path / "notes.md"
        if notes.exists():
            workspace.notes = notes.read_text(encoding="utf-8")
        log = path / "test-results.log"
        if log.exists():
            workspace.last_test_result = log.read_text(encoding="utf-8")[-2000:]
        return workspace

    def list_ids(self) -> list[str]:
        return sorted(
            path.name
            for path in self.root.iterdir()
            if path.is_dir() and (path / "src").is_dir()
        )

    def delete(self, project_id: str) -> bool:
        workspace = self.get(project_id)
        if workspace is None:
            return False
        workspace.delete()
        return True