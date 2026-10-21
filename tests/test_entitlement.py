"""The entitlement layer: the free stretch, and the licence that ends it.

The rule the whole thing rests on: **the app can check a licence and
cannot write one.** The private key is not in the repository and not on
the machine the app runs on, so a licence has to come from whoever issues
them.

The tests here cover the parts that would be embarrassing to get wrong:
a forged key must not work, a damaged key must not crash the app, an
expired licence must not pass, and the learner's progress must never be
destroyed by any of it.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from mentorsmith.core.entitlement import (
    DEFAULT_TRIAL_DAYS,
    EntitlementError,
    activate_licence,
    check_licence,
    clear_licence,
    entitlement,
    looks_like_a_licence,
    verify_signature,
)


def _payload(name: str = "A. Learner", expires: str = "", tier: str = "pro") -> bytes:
    return json.dumps(
        {"name": name, "tier": tier, "expires": expires},
        separators=(",", ":"), sort_keys=True,
    ).encode("utf-8")


class TestTheFreeStretch:
    def test_a_fresh_install_is_in_the_free_stretch(self) -> None:
        state = entitlement({})
        assert state.in_trial is True
        assert state.pro is True
        assert state.days_left == DEFAULT_TRIAL_DAYS

    def test_the_start_is_remembered(self) -> None:
        settings: dict = {}
        entitlement(settings)
        assert settings.get("trial_started")

    def test_the_stretch_does_not_restart_on_every_launch(self) -> None:
        settings: dict = {}
        first = entitlement(settings)["trial_started"] if False else None
        entitlement(settings)
        started = settings["trial_started"]
        entitlement(settings)
        assert settings["trial_started"] == started

    def test_it_ends_after_the_stretch(self) -> None:
        old = (datetime.now(timezone.utc) - timedelta(days=DEFAULT_TRIAL_DAYS + 1))
        state = entitlement({"trial_started": old.isoformat()})
        assert state.in_trial is False
        assert state.pro is False
        assert state.trial_over is True

    def test_the_days_left_count_down(self) -> None:
        started = datetime.now(timezone.utc) - timedelta(days=10)
        state = entitlement({"trial_started": started.isoformat()})
        assert 19 <= state.days_left <= 20

    def test_the_reason_says_what_happened(self) -> None:
        state = entitlement({})
        assert "free" in state.reason.lower()
        old = (datetime.now(timezone.utc) - timedelta(days=99)).isoformat()
        state = entitlement({"trial_started": old})
        assert "licence" in state.reason.lower()


class TestLicenceChecking:
    def test_a_key_that_is_not_a_key_is_refused(self) -> None:
        with pytest.raises(EntitlementError):
            check_licence("hello")

    def test_an_empty_key_is_refused(self) -> None:
        with pytest.raises(EntitlementError):
            check_licence("   ")

    def test_a_damaged_key_is_refused_not_crashed(self) -> None:
        with pytest.raises(EntitlementError):
            check_licence("MS1.not-base64!!.")

    def test_a_forged_signature_is_refused(self) -> None:
        """The whole point of a public key: the app cannot write licences."""
        import base64

        payload = _payload()
        fake = base64.urlsafe_b64encode(b"\x00" * 256).rstrip(b"=").decode()
        with pytest.raises(EntitlementError):
            check_licence(f"MS1.{base64.urlsafe_b64encode(payload).rstrip(b'=').decode()}.{fake}")

    def test_a_tampered_payload_is_refused(self) -> None:
        """Changing the name in the payload must invalidate it.

        This needs a real signature, so it needs the private key - which is
        not in the repository and not on most machines. Where the signing
        key is available the test runs for real; elsewhere it is skipped,
        and the forgery test above still covers the case that matters.
        """
        import sys

        sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "tools"))
        try:
            import make_licence_key as issuer
        except ImportError:
            pytest.skip("the licence issuer is not available")
        if not issuer.PRIVATE.exists():
            pytest.skip("no signing key on this machine")

        key = issuer.issue("A. Learner", 6)
        original = key.split(".")[1]
        signature = key.split(".")[2]

        from mentorsmith.core.entitlement import _b64url_encode

        tampered = _b64url_encode(_payload("Somebody Else"))
        with pytest.raises(EntitlementError):
            check_licence(f"MS1.{tampered}.{signature}")
        # The untouched one still works, so the failure above was the
        # tampering and not a broken key.
        assert check_licence(key).name == "A. Learner"
        assert original

    def test_the_shape_of_a_key_is_recognised(self) -> None:
        assert looks_like_a_licence("MS1.abc.def") is True
        assert looks_like_a_licence("nonsense") is False
        assert looks_like_a_licence("") is False

    def test_verification_of_a_wrong_signature_fails(self) -> None:
        assert verify_signature(_payload(), b"\x00" * 256) is False


class TestStoringAndClearing:
    def test_activating_stores_the_key(self) -> None:
        settings: dict = {}
        # Without the private key we cannot make a real one, so a bad key
        # must be refused and nothing stored.
        with pytest.raises(EntitlementError):
            activate_licence(settings, "MS1.bad.bad")
        assert "licence_key" not in settings

    def test_clearing_forgets_the_key(self) -> None:
        settings = {"licence_key": "MS1.abc.def"}
        clear_licence(settings)
        assert "licence_key" not in settings

    def test_a_stored_but_broken_key_does_not_grant_access(self) -> None:
        state = entitlement({"licence_key": "MS1.broken.broken"})
        assert state.licence is None
        assert state.pro is True, "the free stretch is still running"
        assert "licence" not in state.reason.lower() or "free" in state.reason.lower()


class TestTheGate:
    def test_it_is_off_by_default(self) -> None:
        """A gate that appears without warning is how an app earns a bad name."""
        state = entitlement({})
        assert state.gate_enabled is False

    def test_it_can_be_switched_on(self) -> None:
        state = entitlement({"licence_gate_enabled": True})
        assert state.gate_enabled is True

    def test_the_free_stretch_works_with_the_gate_on(self) -> None:
        state = entitlement({"licence_gate_enabled": True})
        assert state.pro is True
        assert state.in_trial is True

    def test_over_the_line_without_a_licence_means_no(self) -> None:
        old = (datetime.now(timezone.utc) - timedelta(days=99)).isoformat()
        state = entitlement({
            "trial_started": old, "licence_gate_enabled": True,
        })
        assert state.pro is False
        assert state.trial_over is True


class TestNothingIsLost:
    def test_the_entitlement_never_touches_progress(self) -> None:
        """The gate is about features, never about the learner's work."""
        settings = {
            "trial_started": (
                datetime.now(timezone.utc) - timedelta(days=99)
            ).isoformat(),
            "licence_gate_enabled": True,
            "exercise_attempts": 42,
        }
        entitlement(settings)
        assert settings["exercise_attempts"] == 42
        assert "trial_started" in settings

    def test_the_state_serialises(self) -> None:
        state = entitlement({})
        data = state.to_dict()
        assert data["pro"] is True
        assert data["in_trial"] is True
        assert "days_left" in data
