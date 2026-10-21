"""Focus mode: what it can do, and what it says it cannot do.

The design rule is that a focus mode must be **honest about the machine it
is on**. On X11 the window list is available and applications can be closed.
On Wayland the compositor will not let one application see another's windows,
and no amount of trying will change that - so the app says so instead of
pretending.

These tests hold to that, and check that a session can always be ended.
"""

from __future__ import annotations

import os

import pytest

from mentorsmith.services.focus import (
    KNOWN_DISTRACTIONS,
    Distraction,
    FocusMode,
    format_duration,
)


class TestWhatTheMachineCanDo:
    def test_the_display_server_is_named(self) -> None:
        assert FocusMode.display_server() in ("x11", "wayland", "unknown")

    def test_the_window_list_is_only_claimed_on_x11(self, monkeypatch) -> None:
        monkeypatch.setenv("WAYLAND_DISPLAY", "wayland-0")
        monkeypatch.setenv("DISPLAY", ":0")
        assert FocusMode.window_list_available() is False

    def test_x11_can_list_windows(self, monkeypatch) -> None:
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        monkeypatch.setenv("DISPLAY", ":0")
        monkeypatch.setattr(
            "mentorsmith.services.focus.shutil.which",
            lambda name: "/usr/bin/wmctrl" if name == "wmctrl" else None,
        )
        assert FocusMode.window_list_available() is True

    def test_without_a_display_server_nothing_is_claimed(self, monkeypatch) -> None:
        monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
        monkeypatch.delenv("DISPLAY", raising=False)
        assert FocusMode.window_list_available() is False


class TestTheDistractions:
    def test_it_never_lists_the_app_itself(self, monkeypatch) -> None:
        """Closing MentorSmith mid-session would be a strange thing to do."""
        from mentorsmith.services import focus as module

        monkeypatch.setattr(
            module.FocusMode, "_list_windows", lambda self: []
        )
        # The process table is asked in the form "pid command".
        monkeypatch.setattr(
            module.subprocess, "run",
            lambda *a, **k: type(
                "R", (), {
                    "returncode": 0,
                    "stdout": f"{os.getpid()} firefox\n3141 firefox\n",
                    "stderr": "",
                },
            )(),
        )
        found = FocusMode().list_distractions()
        assert all(item.pid != os.getpid() for item in found)

    def test_the_terminal_is_never_a_distraction(self) -> None:
        """Sometimes the terminal is exactly what is needed."""
        from mentorsmith.services.focus import _is_distracting

        assert _is_distracting("gnome-terminal", "gnome-terminal") is False
        assert _is_distracting("code", "code") is False
        assert _is_distracting("foot", "foot") is False

    def test_a_browser_is_a_distraction(self) -> None:
        from mentorsmith.services.focus import _is_distracting

        assert _is_distracting("firefox", "Firefox") is True
        assert _is_distracting("discord", "Discord") is True

    def test_the_known_list_has_readable_names(self) -> None:
        for key, label in KNOWN_DISTRACTIONS.items():
            assert key == key.lower()
            assert label, f"{key} has no readable name"


class TestASession:
    def test_it_starts_and_ends(self) -> None:
        mode = FocusMode()
        session = mode.start(25)
        assert mode.running is True
        assert session.minutes == 25
        mode.end()
        assert mode.running is False

    def test_the_clock_counts_down(self) -> None:
        mode = FocusMode()
        session = mode.start(1)
        assert session.seconds_left <= 60
        assert ":" in session.clock()

    def test_a_session_of_zero_minutes_becomes_one(self) -> None:
        mode = FocusMode()
        session = mode.start(0)
        assert session.minutes == 1

    def test_it_reports_what_it_could_not_do(self, monkeypatch) -> None:
        """On a display server that will not say, it says so."""
        mode = FocusMode()
        monkeypatch.setattr(FocusMode, "window_list_available", staticmethod(lambda: False))
        monkeypatch.setattr(FocusMode, "idle_inhibition_available", staticmethod(lambda: False))
        session = mode.start(5)
        limits = " ".join(session.limits)
        assert "display server" in limits
        assert "systemd-inhibit" in limits

    def test_ending_puts_everything_back(self, monkeypatch) -> None:
        """The inhibitor is stopped, so the machine can sleep again."""
        mode = FocusMode()
        started: list[int] = []
        stopped: list[int] = []

        class FakeProcess:
            pid = 4242

        monkeypatch.setattr(
            FocusMode, "_start_inhibitor",
            lambda self, minutes: started.append(minutes) or 4242,
        )
        monkeypatch.setattr(
            "mentorsmith.services.focus.os.kill",
            lambda pid, sig: stopped.append(pid),
        )
        mode.start(10)
        assert started == [10]
        mode.end()
        assert stopped == [4242]

    def test_a_session_can_always_be_ended(self) -> None:
        """A focus mode you cannot escape is a trap."""
        mode = FocusMode()
        mode.start(1)
        assert mode.end() is not None
        assert mode.session is None


class TestFormatting:
    def test_minutes_read_naturally(self) -> None:
        assert format_duration(1) == "1 minute"
        assert format_duration(45) == "45 minutes"

    def test_hours_read_naturally(self) -> None:
        assert format_duration(60) == "1 hour"
        assert format_duration(90) == "1 hour and 30 minutes"
        assert format_duration(120) == "2 hours"
