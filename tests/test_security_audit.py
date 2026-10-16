"""The security audit must be honest, including when it cannot verify.

The tests here focus on the audit's own behaviour rather than re-running every
slow check: a report that claims more than it verified is the specific failure
mode this module exists to prevent, so that is what is tested.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mentorsmith.services import security_audit as audit_mod
from mentorsmith.services.security_audit import (
    AuditReport,
    Check,
    Status,
    run_audit,
)


class TestCheckSemantics:
    def test_every_check_states_what_it_does_not_prove(self) -> None:
        for factory in audit_mod.ALL_CHECKS:
            check = factory()
            assert check.does_not_prove.strip(), (
                f"{check.name} must state its own limits"
            )

    def test_every_check_states_what_it_proves(self) -> None:
        for factory in audit_mod.ALL_CHECKS:
            assert factory().proves.strip()

    def test_a_check_that_errored_is_a_failure_not_a_skip(self) -> None:
        """A crashing check must not be mistaken for a passing one."""

        def broken() -> Check:
            raise RuntimeError("kaboom")

        report = run_audit(checks=[broken])
        assert len(report.failed) == 1
        assert report.failed[0].status is Status.FAILED
        assert "kaboom" in report.failed[0].detail
        assert "kaboom" in report.verdict or "FAILED" in report.verdict

    def test_a_crashing_check_does_not_abort_the_audit(self) -> None:
        """One broken check must not stop the others from running."""

        def broken() -> Check:
            raise RuntimeError("kaboom")

        report = run_audit(checks=[broken, audit_mod.check_language_isolation])
        assert len(report.checks) == 2
        assert report.failed and report.passed


class TestReportHonesty:
    def test_a_failure_is_reported_first_and_prominently(self) -> None:
        report = AuditReport(
            checks=[
                Check("ok", Status.PASSED, "a thing", "nothing else"),
                Check("bad", Status.FAILED, "a thing", "nothing else"),
            ]
        )
        assert "FAILED" in report.verdict
        # Both are present; the failure is what the verdict leads with.
        assert [c.name for c in report.failed] == ["bad"]
        assert [c.name for c in report.passed] == ["ok"]

    def test_a_skip_never_counts_as_a_pass(self) -> None:
        report = AuditReport(
            checks=[Check("s", Status.SKIPPED, "a thing", "nothing else")]
        )
        assert len(report.passed) == 0
        assert len(report.skipped) == 1
        assert "No containment check could be run" in report.verdict

    def test_the_verdict_never_claims_security(self) -> None:
        report = AuditReport(
            checks=[Check("p", Status.PASSED, "a thing", "nothing else")]
        )
        verdict = report.verdict.lower()
        assert "secure" not in verdict
        assert "not a security boundary" in verdict

    def test_a_skipped_check_is_labelled_skip_not_pass(self) -> None:
        check = Check("s", Status.SKIPPED, "a thing", "nothing else", detail="no tool")
        text = check.describe()
        assert text.startswith("[SKIP]")
        assert "no tool" in text

    def test_passing_shows_proves_and_limits(self) -> None:
        check = Check("p", Status.PASSED, "timeouts work", "nothing about clean exits")
        text = check.describe()
        assert "[PASS]" in text
        assert "Proves: timeouts work" in text
        assert "Does not prove: nothing about clean exits" in text

    def test_summary_includes_the_timestamp_and_platform(self) -> None:
        report = AuditReport(platform="Fedora 44", checks=[])
        text = report.summary()
        assert "Fedora 44" in text
        assert report.ran_at


class TestCredentialCheck:
    """A check that cannot fail is worthless, so prove this one can fail."""

    @pytest.fixture()
    def probe(self):
        # tests/test_security_audit.py -> tests/ -> repo root -> mentorsmith/
        path = Path(__file__).resolve().parent.parent / "mentorsmith" / "_probe.py"
        yield path
        path.unlink(missing_ok=True)

    def test_clean_source_passes(self) -> None:
        check = audit_mod.check_no_credentials_in_code()
        assert check.status is Status.PASSED, check.detail

    def test_a_hard_coded_key_is_caught(self, probe: Path) -> None:
        probe.write_text('API_KEY = "sk-abc123def456ghi789"\n')
        check = audit_mod.check_no_credentials_in_code()
        assert check.status is Status.FAILED
        assert "API_KEY" in check.detail

    def test_a_password_literal_is_caught(self, probe: Path) -> None:
        probe.write_text('password: str = "hunter2hunter2"\n')
        assert audit_mod.check_no_credentials_in_code().status is Status.FAILED

    def test_an_environment_read_is_allowed(self, probe: Path) -> None:
        probe.write_text('import os\nAPI_KEY = os.environ.get("MENTORSMITH_API_KEY")\n')
        assert audit_mod.check_no_credentials_in_code().status is Status.PASSED

    def test_a_getenv_read_is_allowed(self, probe: Path) -> None:
        probe.write_text('import os\ntoken = os.getenv("SOME_TOKEN", "")\n')
        assert audit_mod.check_no_credentials_in_code().status is Status.PASSED

    def test_a_placeholder_is_not_a_secret(self, probe: Path) -> None:
        probe.write_text('api_key = "changeme"\n')
        assert audit_mod.check_no_credentials_in_code().status is Status.PASSED

    def test_the_env_var_name_as_a_default_is_not_a_secret(self, probe: Path) -> None:
        """`api_key_env: str = "MENTORSMITH_API_KEY"` names a variable, not a key."""
        probe.write_text('api_key_env: str = "MENTORSMITH_API_KEY"\n')
        assert audit_mod.check_no_credentials_in_code().status is Status.PASSED

    def test_a_computed_value_is_not_a_literal(self, probe: Path) -> None:
        probe.write_text('API_KEY = load_key_from_vault()\n')
        assert audit_mod.check_no_credentials_in_code().status is Status.PASSED

    def test_a_commented_out_key_is_ignored(self, probe: Path) -> None:
        probe.write_text('# API_KEY = "sk-not-really-here"\n')
        assert audit_mod.check_no_credentials_in_code().status is Status.PASSED

    def test_the_check_ignores_itself(self) -> None:
        """This module names the patterns it searches for; it must not flag itself."""
        check = audit_mod.check_no_credentials_in_code()
        assert "security_audit.py" not in check.detail


class TestLanguageIsolationCheck:
    def test_progress_does_not_leak_between_languages(self) -> None:
        check = audit_mod.check_language_isolation()
        assert check.status is Status.PASSED, check.detail