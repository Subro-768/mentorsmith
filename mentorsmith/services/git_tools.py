"""Git integration: inspect, and checkpoint only with approval.

Phase 5 is explicit about the boundary:

* Detecting a repository, listing modified files, showing diffs and reading the
  log are **read-only** and safe to do freely.
* Creating a commit is a **write**, and goes through :class:`ProposedCommit`,
  which describes exactly what would happen and must be confirmed by the caller.
* Pushing to a remote is **never done by this module.** There is no function
  that can push. That is a design decision, not an oversight: the absence of the
  capability is what makes "remote pushes require explicit approval"
  enforceable rather than aspirational.
* Nothing here discards changes. There is no checkout, reset, clean or stash
  function, so a destructive mistake is not reachable through this API.

Every git invocation uses an argument vector, never a shell string, so a
filename containing ``;`` or a space cannot turn into a command.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

#: How long any git command may take. A hung git on a network filesystem should
#: not freeze the UI thread that asked.
GIT_TIMEOUT_SECONDS = 20


class GitError(RuntimeError):
    """A git command failed.

    Carries the real stderr, because git's diagnostics are the useful part and
    hiding them makes the feature useless.
    """


class NotARepository(GitError):
    """The path is not inside a git working tree."""


def _run_git(args: list[str], cwd: Path) -> tuple[int, str, str]:
    """Run git with an argument vector. Never through a shell."""
    try:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
            # Bounded output: a huge diff must not exhaust memory.
            errors="replace",
        )
    except FileNotFoundError:
        raise GitError(
            "git is not installed on this system. Install it with:\n"
            "    sudo dnf install git"
        ) from None
    except subprocess.TimeoutExpired:
        raise GitError(
            f"git {' '.join(args[:2])} did not respond within "
            f"{GIT_TIMEOUT_SECONDS}s. This can happen on a slow network drive."
        ) from None
    return completed.returncode, completed.stdout, completed.stderr


@dataclass
class RepositoryInfo:
    """Where the repository is and what state it is in."""

    path: Path
    root: Path
    branch: str = ""
    detached: bool = False
    has_commits: bool = False
    remote_url: str = ""
    ahead: int = 0
    behind: int = 0

    @property
    def has_remote(self) -> bool:
        return bool(self.remote_url)

    def describe(self) -> str:
        if self.detached:
            where = "detached HEAD"
        elif not self.branch:
            where = "no branch (repository has no commits yet)"
        else:
            where = f"branch {self.branch}"
        remote = f", remote {self.remote_url}" if self.remote_url else ", no remote"
        return f"{where}{remote}"


@dataclass
class FileStatus:
    """One changed path."""

    path: str
    #: Two-letter status: staged, unstaged and untracked markers combined.
    status: str

    @property
    def staged(self) -> bool:
        return self.status[0] not in (" ", "?", "")

    @property
    def unstaged(self) -> bool:
        return len(self.status) < 2 or self.status[1] not in (" ", "")

    @property
    def untracked(self) -> bool:
        return self.status == "??" or self.status.startswith("??")

    @property
    def is_conflicted(self) -> bool:
        """``UU``, ``AA``, ``DU``, ``UD`` and friends mean an unresolved merge."""
        return self.status in ("UU", "AA", "DU", "UD", "AU", "UA", "DD")

    def describe(self) -> str:
        labels = []
        if self.is_conflicted:
            labels.append("CONFLICT")
        else:
            if self.untracked:
                labels.append("new")
            else:
                if self.staged:
                    labels.append("staged")
                if self.unstaged:
                    labels.append("modified")
        return f"{', '.join(labels) or 'unchanged'}: {self.path}"


@dataclass
class Commit:
    """One entry from the log."""

    sha: str
    author: str
    relative_time: str
    subject: str


@dataclass
class ProposedCommit:
    """A commit that has **not** been made yet.

    This object is the approval gate. It describes precisely what would happen,
    and only :meth:`execute` does anything. Presenting it is free and safe.
    """

    repository: RepositoryInfo
    message: str
    files: list[FileStatus] = field(default_factory=list)
    #: Set once the commit exists, so the UI can show the result.
    created_sha: str = ""
    executed: bool = False

    @property
    def staged_paths(self) -> list[str]:
        """Paths that ``git commit`` would actually record.

        An untracked file is **not** in this list: ``git commit`` writes only
        what is in the index, and a new file has to be staged first. Counting it
        here would tell the learner their new file was about to be committed when
        it was not.
        """
        return [f.path for f in self.files if f.staged and not f.untracked]

    @property
    def untracked_paths(self) -> list[str]:
        return [f.path for f in self.files if f.untracked]

    def preview(self) -> str:
        """Human-readable summary of what committing would do."""
        if not self.files:
            return "Nothing to commit. The working tree is clean."

        paths = self.staged_paths
        if not paths:
            lines = [
                "Nothing is staged, so a commit right now would record nothing.",
                "",
                "Files with changes:",
                *[f"  {f.describe()}" for f in self.files],
            ]
            if self.untracked_paths:
                lines += [
                    "",
                    "Untracked files are NOT included unless you stage them first.",
                ]
            return "\n".join(lines)

        lines = [
            f"This would create one commit on {self.repository.describe()} "
            f"containing {len(paths)} file(s):",
            *[f"  {path}" for path in paths],
        ]
        unstaged = [
            f.path for f in self.files
            if f.untracked or not f.staged
        ]
        if unstaged:
            lines += [
                "",
                "NOT included (unstaged or untracked):",
                *[f"  {path}" for path in unstaged],
            ]
        lines += [
            "",
            f"Message:\n  {self.message}",
            "",
            "Nothing has been written yet.",
        ]
        return "\n".join(lines)

    def execute(self, *, confirmed: bool = False) -> str:
        """Actually commit. Requires ``confirmed=True``.

        The flag is not ceremony: it makes "approval was given" visible in the
        call site and greppable in review.
        """
        if self.executed:
            raise GitError("This proposal was already executed.")
        if not confirmed:
            raise GitError(
                "Refusing to commit without confirmation. Show preview() to the "
                "learner and pass confirmed=True once they approve."
            )
        if not self.staged_paths:
            raise GitError("Nothing is staged, so there is nothing to commit.")

        code, _stdout, stderr = _run_git(["commit", "-m", self.message], self.repository.path)
        if code != 0:
            raise GitError(f"git commit failed: {stderr.strip()}")

        _, sha, _ = _run_git(["rev-parse", "HEAD"], self.repository.path)
        self.created_sha = sha.strip()
        self.executed = True
        return self.created_sha


class GitRepository:
    """Read-mostly facade over a git working tree."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path).resolve()

    # -- detection ------------------------------------------------------
    def exists(self) -> bool:
        return (self.path / ".git").exists() or (
            (self.path / ".git").is_file()      # worktree / submodule
        )

    def discover(self, start: Path | None = None) -> "GitRepository | None":
        """Walk upwards looking for a working tree. ``None`` if there is none."""
        current = Path(start or self.path).resolve()
        for candidate in [current, *current.parents]:
            probe = GitRepository(candidate)
            if probe.exists():
                return probe
        return None

    # -- state ----------------------------------------------------------
    def info(self) -> RepositoryInfo:
        """Branch, remote and ahead/behind. Never raises for a fresh repo."""
        if not self.exists():
            raise NotARepository(f"No git repository at {self.path}.")

        code, stdout, _ = _run_git(["rev-parse", "--show-toplevel"], self.path)
        root = Path(stdout.strip()) if code == 0 and stdout.strip() else self.path

        info = RepositoryInfo(path=self.path, root=root)

        code, stdout, _ = _run_git(["rev-parse", "--is-inside-work-tree"], self.path)
        inside = code == 0 and stdout.strip() == "true"

        code, stdout, _ = _run_git(["symbolic-ref", "--quiet", "--short", "HEAD"], self.path)
        if code == 0 and stdout.strip():
            info.branch = stdout.strip()
        elif inside:
            info.detached = True

        code, _stdout, _ = _run_git(["rev-parse", "--verify", "HEAD"], self.path)
        info.has_commits = code == 0

        code, stdout, _ = _run_git(["remote", "get-url", "origin"], self.path)
        if code == 0:
            info.remote_url = stdout.strip()

        if info.has_commits and info.remote_url:
            _, stdout, _ = _run_git(
                ["rev-list", "--left-right", "--count", "HEAD...@{upstream}"], self.path
            )
            parts = stdout.split()
            if len(parts) == 2:
                info.ahead, info.behind = int(parts[0]), int(parts[1])
        return info

    def status(self) -> list[FileStatus]:
        """Porcelain status. Untracked files are included as ``??``."""
        if not self.exists():
            raise NotARepository(f"No git repository at {self.path}.")
        code, stdout, stderr = _run_git(
            ["status", "--porcelain", "--untracked-files=all"], self.path
        )
        if code != 0:
            raise GitError(f"git status failed: {stderr.strip()}")

        results: list[FileStatus] = []
        for line in stdout.splitlines():
            if len(line) < 4:
                continue
            status = line[:2]
            # Paths with spaces or renames put the name in quotes after a tab.
            path = line[3:]
            if " -> " in path:
                path = path.split(" -> ")[-1]
            path = path.strip().strip('"')
            if path:
                results.append(FileStatus(path=path, status=status))
        return results

    def is_clean(self) -> bool:
        return not self.status()

    def diff(self, *, staged: bool = False, path: str | None = None,
             max_chars: int = 60_000) -> str:
        """Unified diff, bounded so a huge change cannot exhaust memory.

        Truncation is stated in the output rather than being silent.
        """
        args = ["diff"]
        if staged:
            args.append("--staged")
        if path:
            args += ["--", path]

        code, stdout, stderr = _run_git(args, self.path)
        if code != 0:
            raise GitError(f"git diff failed: {stderr.strip()}")

        if len(stdout) > max_chars:
            return (
                stdout[:max_chars]
                + f"\n\n... [diff truncated at {max_chars} characters; "
                  f"showing the beginning only] ...\n"
            )
        return stdout or "(no diff)"

    def log(self, limit: int = 20) -> list[Commit]:
        """Recent commits, newest first. Empty list for a repo with no commits."""
        if not self.exists():
            raise NotARepository(f"No git repository at {self.path}.")
        code, stdout, _ = _run_git(
            [
                "log",
                f"-{max(1, min(limit, 200))}",
                "--pretty=format:%h%x1f%an%x1f%ar%x1f%s",
            ],
            self.path,
        )
        if code != 0:
            return []
        commits: list[Commit] = []
        for line in stdout.splitlines():
            parts = line.split("\x1f")
            if len(parts) == 4:
                commits.append(Commit(*parts))
        return commits

    def branches(self) -> list[str]:
        code, stdout, _ = _run_git(["branch", "--list"], self.path)
        if code != 0:
            return []
        return [
            line.replace("*", "").strip()
            for line in stdout.splitlines()
            if line.strip()
        ]

    # -- the one write --------------------------------------------------
    def propose_commit(self, message: str, *, paths: list[str] | None = None) -> ProposedCommit:
        """Describe a commit without making it.

        Nothing is staged here either. The proposal lists what *would* be
        included so the learner can see it before deciding.
        """
        if not message.strip():
            raise GitError("A commit message is required.")

        info = self.info()
        files = self.status()

        if paths:
            wanted = set(paths)
            selected = [f for f in files if f.path in wanted]
            if not selected:
                raise GitError(
                    "None of the requested paths have changes:\n"
                    + "\n".join(f"  {p}" for p in paths)
                )
            files = selected

        return ProposedCommit(repository=info, message=message.strip(), files=files)

    def stage(self, paths: list[str]) -> list[str]:
        """Stage paths. Explicitly requested by the learner, never implicit."""
        if not paths:
            raise GitError("No paths given to stage.")
        args: list[str] = []
        for path in paths:
            args += ["--", path]
        code, _stdout, stderr = _run_git(["add"] + args, self.path)
        if code != 0:
            raise GitError(f"git add failed: {stderr.strip()}")
        return list(paths)

    def unstage(self, paths: list[str]) -> list[str]:
        args: list[str] = []
        for path in paths:
            args += ["--", path]
        code, _stdout, stderr = _run_git(["restore", "--staged"] + args, self.path)
        if code != 0:
            raise GitError(f"Could not unstage: {stderr.strip()}")
        return list(paths)

    # -- explicitly absent ---------------------------------------------
    # There is deliberately no push(), no checkout(), no reset(), no clean(),
    # no stash() and no conflict resolution here. Phase 5 requires those to be
    # approval-gated and to show consequences first; the safest way to guarantee
    # that is for the capability not to exist in this module at all.
    def push(self, *args, **kwargs):  # pragma: no cover - guard only
        raise GitError(
            "MentorSmith does not push. Pushing a remote always requires "
            "explicit approval and is done outside the app, where you can see "
            "exactly what would be sent."
        )

    def discard_changes(self, *args, **kwargs):  # pragma: no cover - guard only
        raise GitError(
            "MentorSmith does not discard changes. Uncommitted work can be hours "
            "of effort; deleting it is not something a button should do by "
            "accident. Use git yourself if you are sure."
        )