"""Phase 5 developer tools: workspaces, git, review, test generation, audit.

These tests use real git repositories in ``tmp_path`` and real temporary
workspaces. Nothing touches the tutor's own repository or the learner's home
directory, and nothing runs generated code except in an explicitly isolated
``tmp_path``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mentorsmith.core.workspaces import (
    WorkspaceError,
    WorkspaceManager,
    safe_project_id,
)
from mentorsmith.services import review as review_mod
from mentorsmith.services import security_audit as audit_mod
from mentorsmith.services import testgen as testgen_mod
from mentorsmith.services.git_tools import (
    GitError,
    GitRepository,
    NotARepository,
)

GIT_AVAILABLE = subprocess.run(
    ["git", "--version"], capture_output=True, shell=False
).returncode == 0

needs_git = pytest.mark.skipif(not GIT_AVAILABLE, reason="git is not installed")


# ======================================================================
# Workspaces
# ======================================================================
class TestSafeProjectId:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("my project", "my-project"),
            ("My_Project", "my-project"),
            ("hello world!", "hello-world"),
            ("  spaced  ", "spaced"),
            ("UPPER", "upper"),
        ],
    )
    def test_normalises_names(self, raw: str, expected: str) -> None:
        assert safe_project_id(raw) == expected

    @pytest.mark.parametrize("raw", ["", "   ", "...", "!!!", "-", None])
    def test_rejects_names_with_no_alphanumerics(self, raw) -> None:
        with pytest.raises(WorkspaceError):
            safe_project_id(raw)

    def test_caps_length(self) -> None:
        assert len(safe_project_id("x" * 200)) <= 48

    def test_cannot_produce_a_traversal(self) -> None:
        """The output is always a single path segment."""
        result = safe_project_id("../../etc/passwd")
        assert "/" not in result and ".." not in result


class TestWorkspaceManager:
    @pytest.fixture()
    def manager(self, tmp_path: Path) -> WorkspaceManager:
        return WorkspaceManager(tmp_path / "workspaces")

    def test_create_makes_the_layout(self, manager: WorkspaceManager) -> None:
        workspace = manager.create("first", requirements="A number guessing game.")
        assert workspace.layout.source.is_dir()
        assert workspace.layout.tests.is_dir()
        assert (workspace.layout.root / "requirements.md").read_text().strip() == (
            "A number guessing game."
        )

    def test_ids_are_sanitised_on_disk(self, manager: WorkspaceManager) -> None:
        workspace = manager.create("My Project")
        assert workspace.layout.root.name == "my-project"

    def test_traversal_id_stays_inside_the_root(self, manager: WorkspaceManager) -> None:
        workspace = manager.create("../../escape")
        assert workspace.layout.root.parent == manager.root
        assert str(workspace.layout.root).startswith(str(manager.root))

    def test_write_refuses_to_escape_the_source_directory(self, manager) -> None:
        workspace = manager.create("escape-attempt")
        with pytest.raises(WorkspaceError, match="outside the workspace"):
            workspace.write_source("../../pwned.py", "print('nope')")
        assert not (manager.root.parent / "pwned.py").exists()

    def test_write_refuses_an_absolute_path(self, manager) -> None:
        workspace = manager.create("abs-attempt")
        with pytest.raises(WorkspaceError):
            workspace.write_source("/tmp/should-not-happen.py", "x = 1")

    def test_write_allows_a_nested_path_inside(self, manager) -> None:
        workspace = manager.create("nested")
        path = workspace.write_source("pkg/module.py", "x = 1\n")
        assert path.exists()
        assert path.parent.name == "pkg"

    def test_get_returns_none_when_absent(self, manager) -> None:
        assert manager.get("never-made") is None

    def test_get_reloads_saved_state(self, manager) -> None:
        manager.create("keeper", requirements="Needs a menu.")
        manager.get("keeper").record_notes("Learned about while loops.")
        manager.get("keeper").record_test_result("2 passed, 0 failed")

        reloaded = manager.get("keeper")
        assert reloaded is not None
        assert "while loops" in reloaded.notes
        assert "2 passed" in reloaded.last_test_result

    def test_list_ids(self, manager) -> None:
        manager.create("beta")
        manager.create("alpha")
        assert manager.list_ids() == ["alpha", "beta"]

    def test_list_files_finds_everything(self, manager) -> None:
        workspace = manager.create("listed")
        workspace.write_source("main.py", "x = 1\n")
        workspace.write_test("test_main.py", "def test(): pass\n")
        files = workspace.list_files()
        assert "src/main.py" in files
        assert "tests/test_main.py" in files

    def test_delete_removes_only_that_workspace(self, manager) -> None:
        manager.create("keep")
        manager.create("drop")
        assert manager.delete("drop") is True
        assert manager.list_ids() == ["keep"]

    def test_delete_of_a_missing_workspace_reports_false(self, manager) -> None:
        assert manager.delete("never-existed") is False


# ======================================================================
# Git
# ======================================================================
@pytest.fixture()
def repo(tmp_path: Path) -> GitRepository:
    """A real git repository with one commit."""
    root = tmp_path / "repo"
    root.mkdir()
    run = lambda *args: subprocess.run(  # noqa: E731
        ["git", *args], cwd=root, capture_output=True, text=True, check=True
    )
    run("init", "-q", "-b", "main")
    run("config", "user.email", "test@localhost")
    run("config", "user.name", "Test")
    (root / "README.md").write_text("hello\n")
    run("add", "README.md")
    run("commit", "-qm", "initial commit")
    return GitRepository(root)


@needs_git
class TestGitDetection:
    def test_detects_a_repository(self, repo: GitRepository) -> None:
        assert repo.exists()
        assert repo.discover() is not None

    def test_detects_from_a_subdirectory(self, repo: GitRepository) -> None:
        nested = repo.path / "a" / "b"
        nested.mkdir(parents=True)
        found = GitRepository(nested).discover()
        assert found is not None
        assert found.path == repo.path

    def test_reports_none_when_there_is_no_repository(self, tmp_path: Path) -> None:
        plain = tmp_path / "not-a-repo"
        plain.mkdir()
        assert GitRepository(plain).discover() is None

    def test_info_describes_the_branch(self, repo: GitRepository) -> None:
        info = repo.info()
        assert info.branch in ("main", "master")
        assert info.has_commits
        assert "no remote" in info.describe()

    def test_info_reports_no_remote_by_default(self, repo: GitRepository) -> None:
        assert repo.info().has_remote is False

    def test_info_reports_a_remote(self, repo: GitRepository) -> None:
        subprocess.run(
            ["git", "remote", "add", "origin", "https://example.invalid/x.git"],
            cwd=repo.path, capture_output=True, check=True,
        )
        info = repo.info()
        assert info.has_remote
        assert "example.invalid" in info.remote_url

    def test_operations_on_a_non_repository_fail_clearly(self, tmp_path: Path) -> None:
        plain = tmp_path / "plain"
        plain.mkdir()
        with pytest.raises(NotARepository):
            GitRepository(plain).status()

    def test_a_fresh_repo_with_no_commits(self, tmp_path: Path) -> None:
        root = tmp_path / "fresh"
        root.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=root, capture_output=True, check=True)
        info = GitRepository(root).info()
        assert info.has_commits is False
        assert GitRepository(root).log() == []


@needs_git
class TestGitInspection:
    def test_status_is_clean_initially(self, repo: GitRepository) -> None:
        assert repo.is_clean()

    def test_status_reports_a_modified_file(self, repo: GitRepository) -> None:
        (repo.path / "README.md").write_text("changed\n")
        statuses = repo.status()
        assert len(statuses) == 1
        assert statuses[0].path == "README.md"
        assert statuses[0].unstaged

    def test_status_reports_an_untracked_file(self, repo: GitRepository) -> None:
        (repo.path / "new.txt").write_text("new\n")
        statuses = repo.status()
        assert statuses[0].untracked
        assert "new" in statuses[0].describe()

    def test_diff_shows_the_change(self, repo: GitRepository) -> None:
        (repo.path / "README.md").write_text("before\nafter\n")
        diff = repo.diff()
        assert "+after" in diff

    def test_diff_is_bounded_and_says_so(self, repo: GitRepository) -> None:
        # Modify a *tracked* file: `git diff` does not show untracked ones, so
        # writing a new file would test nothing.
        (repo.path / "README.md").write_text("x" * 50_000)
        diff = repo.diff(max_chars=2_000)
        assert "truncated" in diff
        assert len(diff) < 5_000

    def test_diff_on_a_clean_tree_says_so(self, repo: GitRepository) -> None:
        assert repo.diff() == "(no diff)"

    def test_log_returns_commits(self, repo: GitRepository) -> None:
        commits = repo.log()
        assert len(commits) == 1
        assert commits[0].subject == "initial commit"
        assert len(commits[0].sha) >= 7

    def test_branches_are_listed(self, repo: GitRepository) -> None:
        assert repo.branches()

    def test_a_filename_with_shell_metacharacters_is_handled(self, repo) -> None:
        """A filename must not become a command: git is never called via a shell."""
        nasty = repo.path / "a; rm -rf x.txt"
        nasty.write_text("harmless\n")
        (repo.path / "README.md").write_text("touched\n")
        statuses = repo.status()
        assert any("a; rm -rf x.txt" == s.path for s in statuses)
        assert (repo.path / "README.md").exists(), "the other file survived"


@needs_git
class TestGitApprovalGate:
    def test_proposal_writes_nothing(self, repo: GitRepository) -> None:
        (repo.path / "file.txt").write_text("content\n")
        before = len(repo.log())
        repo.propose_commit("add a file")
        assert len(repo.log()) == before

    def test_preview_states_nothing_has_been_written(self, repo) -> None:
        (repo.path / "file.txt").write_text("content\n")
        repo.stage(["file.txt"])
        proposal = repo.propose_commit("add a file")
        preview = proposal.preview()
        assert "Nothing has been written yet" in preview
        assert "file.txt" in preview

    def test_execute_without_confirmation_is_refused(self, repo: GitRepository) -> None:
        (repo.path / "file.txt").write_text("content\n")
        repo.stage(["file.txt"])
        proposal = repo.propose_commit("add a file")
        with pytest.raises(GitError, match="without confirmation"):
            proposal.execute()
        assert len(repo.log()) == 1, "a commit happened without approval"

    def test_confirmed_execution_commits(self, repo: GitRepository) -> None:
        (repo.path / "file.txt").write_text("content\n")
        repo.stage(["file.txt"])
        proposal = repo.propose_commit("add a file")
        sha = proposal.execute(confirmed=True)
        assert sha
        assert len(repo.log()) == 2
        assert repo.log()[0].subject == "add a file"

    def test_a_proposal_cannot_be_executed_twice(self, repo) -> None:
        (repo.path / "f.txt").write_text("x\n")
        repo.stage(["f.txt"])
        proposal = repo.propose_commit("once")
        proposal.execute(confirmed=True)
        with pytest.raises(GitError, match="already executed"):
            proposal.execute(confirmed=True)

    def test_an_empty_message_is_refused(self, repo) -> None:
        with pytest.raises(GitError, match="message is required"):
            repo.propose_commit("   ")

    def test_nothing_staged_means_nothing_committed(self, repo) -> None:
        (repo.path / "unstaged.txt").write_text("x\n")
        proposal = repo.propose_commit("should not happen")
        with pytest.raises(GitError, match="Nothing is staged"):
            proposal.execute(confirmed=True)
        assert len(repo.log()) == 1

    def test_an_untracked_file_is_not_claimed_as_about_to_be_committed(self, repo) -> None:
        """`git commit` records the index only; a new file must be staged first."""
        (repo.path / "brand_new.txt").write_text("x\n")
        proposal = repo.propose_commit("add it")
        assert "brand_new.txt" not in proposal.staged_paths
        assert proposal.untracked_paths == ["brand_new.txt"]
        assert "Untracked files are NOT included" in proposal.preview()

    def test_a_modified_but_unstaged_file_is_not_claimed(self, repo) -> None:
        (repo.path / "README.md").write_text("edited\n")
        proposal = repo.propose_commit("edit")
        assert proposal.staged_paths == []
        assert "Nothing is staged" in proposal.preview()

    def test_preview_warns_when_nothing_is_staged(self, repo) -> None:
        (repo.path / "unstaged.txt").write_text("x\n")
        preview = repo.propose_commit("msg").preview()
        assert "Nothing is staged" in preview
        assert "unstaged.txt" in preview

    def test_preview_on_a_clean_tree(self, repo) -> None:
        assert "clean" in repo.propose_commit("msg").preview()

    def test_an_empty_message_in_a_clean_tree(self, repo) -> None:
        assert repo.propose_commit("m").files == []

    def test_staging_and_unstaging(self, repo) -> None:
        (repo.path / "f.txt").write_text("x\n")
        repo.stage(["f.txt"])
        assert repo.status()[0].staged
        repo.unstage(["f.txt"])
        assert not repo.status()[0].staged

    def test_proposing_unknown_paths_is_refused(self, repo) -> None:
        with pytest.raises(GitError, match="None of the requested paths"):
            repo.propose_commit("msg", paths=["does-not-exist.txt"])

    def test_staging_nothing_is_refused(self, repo) -> None:
        with pytest.raises(GitError, match="No paths"):
            repo.stage([])


@needs_git
class TestGitAbsentCapabilities:
    """Phase 5 requires these to be approval-gated. Here they simply do not exist."""

    def test_push_is_refused(self, repo: GitRepository) -> None:
        with pytest.raises(GitError, match="does not push"):
            repo.push("origin", "main")

    def test_discard_is_refused(self, repo: GitRepository) -> None:
        with pytest.raises(GitError, match="does not discard"):
            repo.discard_changes("README.md")

    @pytest.mark.parametrize(
        "forbidden", ["checkout", "reset", "clean", "stash", "rebase", "merge"]
    )
    def test_no_destructive_method_is_exposed(self, repo, forbidden: str) -> None:
        assert not hasattr(GitRepository, forbidden), (
            f"{forbidden} is reachable; that needs approval-gating first"
        )


# ======================================================================
# AI code review
# ======================================================================
class TestReviewFindings:
    def _finding(self, **kwargs):
        defaults = dict(
            file="a.py", line=1, title="t", explanation="e",
            importance=review_mod.Importance.MEDIUM,
            category=review_mod.Category.CORRECTNESS,
            origin=review_mod.Origin.SPECULATIVE,
        )
        defaults.update(kwargs)
        return review_mod.Finding(**defaults)

    def test_only_confirmed_findings_are_defects(self) -> None:
        confirmed = self._finding(origin=review_mod.Origin.CONFIRMED)
        heuristic = self._finding(origin=review_mod.Origin.HEURISTIC)
        speculative = self._finding(origin=review_mod.Origin.SPECULATIVE)
        assert confirmed.is_defect
        assert not heuristic.is_defect
        assert not speculative.is_defect

    def test_unverified_findings_always_show_how_to_check(self) -> None:
        text = self._finding().describe()
        assert "Verify by:" in text

    def test_confirmed_findings_do_not_need_a_verify_line(self) -> None:
        text = self._finding(origin=review_mod.Origin.CONFIRMED).describe()
        assert "CONFIRMED" in text
        assert "Verify by:" not in text

    def test_location_includes_the_line(self) -> None:
        assert self._finding(line=42).location == "a.py:42"

    def test_location_without_a_line(self) -> None:
        assert self._finding(line=None).location == "a.py"


class TestPythonReview:
    def test_finds_a_bare_except(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.py"
        path.write_text("try:\n    x = 1\nexcept:\n    pass\n")
        findings = review_mod.review_python_file(path)
        assert any("bare except" in f.title for f in findings)

    def test_finds_a_specific_except_as_acceptable(self, tmp_path: Path) -> None:
        path = tmp_path / "ok.py"
        path.write_text("try:\n    x = 1\nexcept ValueError:\n    pass\n")
        findings = review_mod.review_python_file(path)
        assert not any("bare except" in f.title for f in findings)

    def test_finds_eval(self, tmp_path: Path) -> None:
        path = tmp_path / "eval.py"
        path.write_text("y = eval(user_input)\n")
        assert any("eval" in f.title for f in review_mod.review_python_file(path))

    def test_finds_shell_true(self, tmp_path: Path) -> None:
        path = tmp_path / "sh.py"
        path.write_text(
            "import subprocess\nsubprocess.run(cmd, shell=True)\n"
        )
        assert any("shell=True" in f.title for f in review_mod.review_python_file(path))

    def test_finds_a_mutable_default(self, tmp_path: Path) -> None:
        path = tmp_path / "mut.py"
        path.write_text("def f(items=[]):\n    return items\n")
        assert any(
            "mutable default" in f.title for f in review_mod.review_python_file(path)
        )

    def test_immutable_default_is_fine(self, tmp_path: Path) -> None:
        path = tmp_path / "ok.py"
        path.write_text("def f(name=\"x\"):\n    return name\n")
        assert not any(
            "mutable default" in f.title for f in review_mod.review_python_file(path)
        )

    def test_finds_a_swallowed_exception(self, tmp_path: Path) -> None:
        path = tmp_path / "swallow.py"
        path.write_text("try:\n    x = 1\nexcept ValueError:\n    pass\n")
        assert any(
            "swallowed" in f.title for f in review_mod.review_python_file(path)
        )

    def test_a_syntax_error_is_confirmed_not_heuristic(self, tmp_path: Path) -> None:
        path = tmp_path / "broken.py"
        path.write_text("def f(:\n    pass\n")
        findings = review_mod.review_python_file(path)
        assert findings, "a file that cannot parse must be reported"
        assert all(f.origin is review_mod.Origin.CONFIRMED for f in findings)

    def test_clean_code_yields_nothing(self, tmp_path: Path) -> None:
        path = tmp_path / "clean.py"
        path.write_text("def add(a: int, b: int) -> int:\n    return a + b\n")
        assert review_mod.review_python_file(path) == []


class TestCppReview:
    def test_finds_strcpy(self, tmp_path: Path) -> None:
        path = tmp_path / "x.cpp"
        path.write_text("#include <string.h>\nvoid f(char*d,char*s){strcpy(d,s);}\n")
        assert any("strcpy" in f.title for f in review_mod.review_cpp_file(path))

    def test_finds_system(self, tmp_path: Path) -> None:
        path = tmp_path / "x.cpp"
        path.write_text("#include <cstdlib>\nvoid f(){ system(\"ls\"); }\n")
        assert any("system" in f.title for f in review_mod.review_cpp_file(path))

    def test_heuristics_are_never_marked_confirmed(self, tmp_path: Path) -> None:
        path = tmp_path / "x.cpp"
        path.write_text("void f(){ char*p = (char*)malloc(10); }\n")
        findings = review_mod.review_cpp_file(path)
        assert findings
        assert all(f.origin is not review_mod.Origin.CONFIRMED for f in findings)

    def test_cpp_compiler_diagnostics_are_confirmed(self, tmp_path: Path) -> None:
        import shutil as _shutil

        if not _shutil.which("g++"):
            pytest.skip("g++ is not installed")
        path = tmp_path / "broken.cpp"
        path.write_text("int main() { int x = ; return 0; }\n")
        findings, command = review_mod.compile_and_review(path, relative_to=tmp_path)
        assert findings
        assert all(f.origin is review_mod.Origin.CONFIRMED for f in findings)
        assert "-Wall" in (command or "")

    def test_correct_cpp_has_no_confirmed_findings(self, tmp_path: Path) -> None:
        import shutil as _shutil

        if not _shutil.which("g++"):
            pytest.skip("g++ is not installed")
        path = tmp_path / "ok.cpp"
        path.write_text("int main() { return 0; }\n")
        findings, _ = review_mod.compile_and_review(path, relative_to=tmp_path)
        assert findings == []


class TestReviewReporting:
    def test_summary_counts_by_origin(self) -> None:
        report = review_mod.ReviewReport(files_reviewed=["a.py"])
        base = dict(file="a.py", title="t", explanation="e")
        report.findings = [
            review_mod.Finding(**base, line=1, importance=review_mod.Importance.HIGH,
                               category=review_mod.Category.CORRECTNESS,
                               origin=review_mod.Origin.CONFIRMED),
            review_mod.Finding(**base, line=2, importance=review_mod.Importance.LOW,
                               category=review_mod.Category.MAINTAINABILITY,
                               origin=review_mod.Origin.SPECULATIVE),
        ]
        assert report.counts() == {"confirmed": 1, "heuristic": 0, "speculative": 1}
        assert len(report.defects) == 1

    def test_confirmed_findings_sort_first(self) -> None:
        report = review_mod.ReviewReport()
        base = dict(file="a.py", title="t", explanation="e")
        report.findings = [
            review_mod.Finding(**base, line=9, importance=review_mod.Importance.LOW,
                               category=review_mod.Category.MAINTAINABILITY,
                               origin=review_mod.Origin.SPECULATIVE),
            review_mod.Finding(**base, line=1, importance=review_mod.Importance.HIGH,
                               category=review_mod.Category.CORRECTNESS,
                               origin=review_mod.Origin.CONFIRMED),
        ]
        assert report.sorted_findings()[0].origin is review_mod.Origin.CONFIRMED

    def test_verdict_never_says_secure(self) -> None:
        report = review_mod.ReviewReport(files_reviewed=["a"])
        report.findings = [
            review_mod.Finding(file="a", line=1, title="t", explanation="e",
                               importance=review_mod.Importance.HIGH,
                               category=review_mod.Category.CORRECTNESS,
                               origin=review_mod.Origin.CONFIRMED)
        ]
        text = report.describe().lower()
        assert "secure" not in text

    def test_empty_report_is_fine(self) -> None:
        report = review_mod.ReviewReport()
        assert report.counts()["confirmed"] == 0
        assert "No findings" in report.summary()


class TestReviewParsing:
    def test_parsed_ai_findings_are_always_speculative(self) -> None:
        response = (
            "file: main.py\n"
            "line: 12\n"
            "importance: high\n"
            "category: correctness\n"
            "issue: The loop never terminates when x is 0.\n"
            "  The condition should be <=.\n"
            "fix: Use while x <= 10\n"
            "verify: Run with x=0\n"
        )
        findings = review_mod.parse_review_response(response)
        assert len(findings) == 1
        assert findings[0].origin is review_mod.Origin.SPECULATIVE
        assert findings[0].importance is review_mod.Importance.HIGH
        assert findings[0].line == 12
        assert "terminates" in findings[0].title or "terminates" in findings[0].explanation

    def test_a_parsable_field_cannot_be_trusted_into_confirmed(self) -> None:
        """Even if a model writes 'confirmed', the parser must not believe it."""
        response = "file: a.py\norigin: confirmed\nimportance: high\nissue: boom\n"
        findings = review_mod.parse_review_response(response)
        assert all(f.origin is review_mod.Origin.SPECULATIVE for f in findings)

    def test_empty_response_yields_nothing(self) -> None:
        assert review_mod.parse_review_response("") == []

    def test_chatty_response_does_not_raise(self) -> None:
        assert review_mod.parse_review_response("Sure! Here are my thoughts.") == []

    def test_unparseable_importance_defaults_to_medium(self) -> None:
        response = "file: a.py\nimportance: enormous\nissue: something\n"
        findings = review_mod.parse_review_response(response)
        assert findings[0].importance is review_mod.Importance.MEDIUM

    def test_merging_keeps_origins_distinct(self) -> None:
        static = review_mod.ReviewReport(
            files_reviewed=["a.py"],
            findings=[
                review_mod.Finding(file="a.py", line=1, title="c", explanation="e",
                                   importance=review_mod.Importance.HIGH,
                                   category=review_mod.Category.CORRECTNESS,
                                   origin=review_mod.Origin.CONFIRMED)
            ],
        )
        ai = review_mod.parse_review_response("file: a.py\nissue: maybe\n")
        merged = review_mod.merge_reports(static, ai)
        assert merged.counts() == {"confirmed": 1, "heuristic": 0, "speculative": 1}


# ======================================================================
# Test generation
# ======================================================================
class TestTestGeneration:
    RESPONSE = (
        "Here are the tests.\n\n"
        "```\nkind: normal\nname: test_returns_sum\nwhy: the basic path\n"
        "code:\n\ndef test_returns_sum():\n    assert add(1, 2) == 3\n```\n\n"
        "```\nkind: boundary\nname: test_zero\nwhy: off by one lives here\n"
        "code:\n\ndef test_zero():\n    assert add(0, 0) == 0\n```\n\n"
        "```\nkind: expected_failure\nname: test_rejects_negative\n"
        "why: the validator is never exercised\n"
        "code:\n\ndef test_rejects_negative():\n    raise ValueError('no')\n```\n"
    )

    def test_parses_each_proposed_case(self) -> None:
        report = testgen_mod.parse_testgen_response(self.RESPONSE)
        assert len(report.proposed) == 3
        assert {t.kind for t in report.proposed} == {
            testgen_mod.CaseKind.NORMAL,
            testgen_mod.CaseKind.BOUNDARY,
            testgen_mod.CaseKind.EXPECTED_FAILURE,
        }

    def test_proposed_tests_are_not_executed(self) -> None:
        report = testgen_mod.parse_testgen_response(self.RESPONSE)
        assert all(not t.executed for t in report.proposed)
        assert "PROPOSED" in report.proposed[0].describe()

    def test_a_regression_case_is_labelled(self) -> None:
        report = testgen_mod.parse_testgen_response(
            "```\nkind: prior_bug\nname: test_off_by_one\ncode:\nx = 1\n```\n"
        )
        assert report.proposed[0].is_regression
        assert "prior bug" in report.proposed[0].kind.label

    def test_an_unknown_kind_is_reported_not_crashed(self) -> None:
        report = testgen_mod.parse_testgen_response(
            "```\nkind: moon_phase\nname: t\ncode:\nx = 1\n```\n"
        )
        assert report.proposed[0].kind is testgen_mod.CaseKind.NORMAL
        assert report.errors

    def test_a_case_with_no_code_is_skipped_and_reported(self) -> None:
        report = testgen_mod.parse_testgen_response(
            "```\nkind: normal\nname: empty\ncode:\n```\n"
        )
        assert report.proposed == []
        assert report.errors

    def test_coverage_gaps_are_named(self) -> None:
        report = testgen_mod.parse_testgen_response(self.RESPONSE)
        gaps = report.coverage_gaps()
        assert any("invalid input" in g for g in gaps)
        assert any("prior bug" in g for g in gaps)

    def test_no_gaps_when_all_kinds_are_covered(self) -> None:
        blocks = "".join(
            f"```\nkind: {k.value}\nname: t_{k.value}\ncode:\nx = 1\n```\n"
            for k in testgen_mod.CaseKind
        )
        assert testgen_mod.parse_testgen_response(blocks).coverage_gaps() == []

    def test_summary_disclaims_completeness(self) -> None:
        report = testgen_mod.parse_testgen_response(self.RESPONSE)
        assert "does not prove" in report.summary()

    def test_summary_separates_executed_from_proposed(self) -> None:
        report = testgen_mod.parse_testgen_response(self.RESPONSE)
        report.proposed[0].executed = True
        report.proposed[0].passed = True
        assert "1 executed" in report.summary()
        assert "2 not yet run" in report.summary()

    def test_empty_response_is_reported(self) -> None:
        report = testgen_mod.parse_testgen_response("")
        assert report.proposed == []
        assert report.errors

    def test_no_tests_proposed_is_stated(self) -> None:
        assert "No tests were proposed" in testgen_mod.parse_testgen_response(
            ""
        ).summary()


class TestTestExecution:
    def test_execution_requires_confirmation(self, tmp_path: Path) -> None:
        test = testgen_mod.ProposedTest(
            kind=testgen_mod.CaseKind.NORMAL,
            name="t",
            source="raise AssertionError('boom')\n",
            language=testgen_mod.Language.PYTHON,
        )
        with pytest.raises(PermissionError, match="without confirmation"):
            test.execute(work_dir=tmp_path)

    def test_a_confirmed_test_runs_and_records_the_result(self, tmp_path: Path) -> None:
        test = testgen_mod.ProposedTest(
            kind=testgen_mod.CaseKind.NORMAL,
            name="passing",
            source="print('all good')\n",
            language=testgen_mod.Language.PYTHON,
        )
        passed = test.execute(work_dir=tmp_path / "w", confirmed=True)
        assert passed
        assert test.executed and test.passed
        assert "all good" in test.output

    def test_a_failing_test_is_recorded_as_failed(self, tmp_path: Path) -> None:
        test = testgen_mod.ProposedTest(
            kind=testgen_mod.CaseKind.NORMAL,
            name="failing",
            source="raise AssertionError('boom')\n",
            language=testgen_mod.Language.PYTHON,
        )
        assert not test.execute(work_dir=tmp_path / "w", confirmed=True)
        assert test.executed and not test.passed

    def test_a_runaway_generated_test_is_stopped(self, tmp_path: Path) -> None:
        test = testgen_mod.ProposedTest(
            kind=testgen_mod.CaseKind.NORMAL,
            name="spin",
            source="while True:\n    pass\n",
            language=testgen_mod.Language.PYTHON,
        )
        started = test.execute(work_dir=tmp_path / "w", confirmed=True, timeout=2)
        assert started is False, "a hanging test must not hang the audit"

    def test_saving_goes_to_the_workspace_not_the_app(self, tmp_path: Path) -> None:
        manager = WorkspaceManager(tmp_path / "ws")
        workspace = manager.create("generated")
        report = testgen_mod.parse_testgen_response(
            "```\nkind: normal\nname: t_one\ncode:\ndef t(): pass\n```\n"
        )
        written = testgen_mod.save_proposed_tests(report, workspace)
        assert written
        for path in written:
            assert str(path).startswith(str(workspace.layout.tests))
        assert report.proposed[0].saved_to