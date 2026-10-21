"""Focus mode: stop the things that pull you away, for a set time.

What "stop all distracting apps" can actually mean on Linux
-----------------------------------------------------------
It depends on the display server, and the honest answer differs:

**X11** — the window list is available. ``wmctrl`` can enumerate every
window with its title, its application and its process id, and can ask an
application to close. A session can therefore actually close the
distractions you name.

**Wayland** — the compositor deliberately does not let one client see or
close another's windows. There is no way to enumerate another app's
windows, and saying otherwise would be a lie. What still works is closing
*processes* by name, which is why this module lists recognisable
distractions from the process table when the window list is unavailable.

**Everywhere** — two things always work, and they are the ones that
matter most:

* the **guard**: a full-screen window the app puts up, so the other
  windows are not what you are looking at;
* **idle inhibition**: the screen does not blank and the machine does not
  suspend, through ``systemd-inhibit``.

So a focus session always does something useful, and says plainly what it
could not do.

Android
-------
Android has a real, supported equivalent: **Do Not Disturb**. The app
requests *notification policy access* - a permission the user grants once -
and then sets the interruption filter to priority-only, which silences
notifications from every other app. See ``FocusMode.kt`` on the Android
side; this module is the desktop half of the same idea.
"""

from __future__ import annotations

import os
import re
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

#: Applications that are commonly the reason a study session falls apart.
#:
#: Used only when the window list is unavailable. The list is a heuristic
#: and the UI says so.
KNOWN_DISTRACTIONS: dict[str, str] = {
    "firefox": "Firefox",
    "google-chrome": "Chrome",
    "chromium": "Chromium",
    "brave": "Brave",
    "opera": "Opera",
    "vivaldi": "Vivaldi",
    "discord": "Discord",
    "telegram": "Telegram",
    "signal": "Signal",
    "slack": "Slack",
    "whatsapp": "WhatsApp",
    "steam": "Steam",
    "spotify": "Spotify",
    "vlc": "VLC",
    "mpv": "mpv",
    "obs": "OBS",
    "zoom": "Zoom",
    "teams": "Teams",
    "element": "Element",
    "pidgin": "Pidgin",
}


@dataclass
class Distraction:
    """Something running that is probably not what you should be doing."""

    #: A stable-ish identifier: the window id on X11, else the process name.
    key: str
    #: What to show the learner.
    label: str
    #: The window title, when there is one.
    title: str = ""
    #: The process id, when it is known.
    pid: int | None = None
    #: How it was found: "window" (real, from the WM) or "process" (guessed).
    source: str = "process"

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "title": self.title,
            "pid": self.pid,
            "source": self.source,
        }


@dataclass
class FocusSession:
    """A running focus session."""

    minutes: int
    started_at: float
    #: The process id of the ``systemd-inhibit`` helper, if one was started.
    inhibitor_pid: int | None = None
    #: Whether the screen lock and suspend were actually inhibited.
    idle_inhibited: bool = False
    #: What was closed when the session started.
    closed: list[str] = field(default_factory=list)
    #: Anything that could not be done, said plainly.
    limits: list[str] = field(default_factory=list)

    @property
    def seconds_left(self) -> int:
        return max(0, int(self.started_at + self.minutes * 60 - time.monotonic()))

    @property
    def finished(self) -> bool:
        return self.seconds_left <= 0

    def clock(self) -> str:
        minutes, seconds = divmod(self.seconds_left, 60)
        return f"{minutes:02d}:{seconds:02d}"


class FocusMode:
    """Starts and stops a focus session.

    Nothing here is destructive without being asked for: closing an
    application is the learner's decision, made by ticking it, and
    everything the session changes is put back when it ends.
    """

    def __init__(self) -> None:
        self._session: FocusSession | None = None

    # ------------------------------------------------------------------
    # What the machine can do
    # ------------------------------------------------------------------
    @staticmethod
    def window_list_available() -> bool:
        """Whether the display server will tell us what is on screen."""
        return shutil.which("wmctrl") is not None and _is_x11()

    @staticmethod
    def idle_inhibition_available() -> bool:
        return shutil.which("systemd-inhibit") is not None

    @staticmethod
    def display_server() -> str:
        """"x11", "wayland" or "unknown"."""
        if _is_wayland():
            return "wayland"
        if _is_x11():
            return "x11"
        return "unknown"

    # ------------------------------------------------------------------
    # Finding distractions
    # ------------------------------------------------------------------
    def list_distractions(self) -> list[Distraction]:
        """The running applications that look like distractions.

        On X11 these are the real windows, with their titles. On Wayland
        there is no way to ask, so this falls back to the process table and
        matches known application names - which is a guess, and the UI says
        so.
        """
        found = self._list_windows()
        if found:
            return found
        return self._list_known_processes()

    def _list_windows(self) -> list[Distraction]:
        if not shutil.which("wmctrl"):
            return []
        try:
            result = subprocess.run(
                ["wmctrl", "-lp"], capture_output=True, text=True, timeout=10
            )
        except (OSError, subprocess.SubprocessError):
            return []
        if result.returncode != 0:
            return []
        distractions: list[Distraction] = []
        for line in result.stdout.splitlines():
            parts = line.split(None, 4)
            if len(parts) < 5:
                continue
            window_id, _desktop, pid_text, program, title = parts
            try:
                pid = int(pid_text)
            except ValueError:
                pid = None
            key = f"window:{window_id}"
            label = _friendly_name(program)
            # Only offer what is plausibly a distraction; a terminal or the
            # file manager is often exactly what the learner needs.
            if not _is_distracting(program, label):
                continue
            distractions.append(Distraction(
                key=key, label=label, title=title.strip(), pid=pid, source="window"
            ))
        return distractions

    def _list_known_processes(self) -> list[Distraction]:
        """Guess from the process table, for when the WM will not say."""
        try:
            result = subprocess.run(
                ["ps", "-eo", "pid=,comm="], capture_output=True, text=True, timeout=10
            )
        except (OSError, subprocess.SubprocessError):
            return []
        found: list[Distraction] = []
        for line in result.stdout.splitlines():
            parts = line.split(None, 1)
            if len(parts) != 2:
                continue
            pid_text, command = parts
            name = Path(command.strip()).name
            if name not in KNOWN_DISTRACTIONS:
                continue
            try:
                pid = int(pid_text)
            except ValueError:
                continue
            if pid == os.getpid():
                continue
            found.append(Distraction(
                key=f"process:{name}",
                label=KNOWN_DISTRACTIONS[name],
                pid=pid,
                source="process",
            ))
        return found

    # ------------------------------------------------------------------
    # Running a session
    # ------------------------------------------------------------------
    def start(
        self,
        minutes: int,
        close: list[Distraction] | None = None,
    ) -> FocusSession:
        """Begin a session, closing what the learner nominated."""
        minutes = max(1, int(minutes))
        session = FocusSession(minutes=minutes, started_at=time.monotonic())

        if not self.window_list_available():
            session.limits.append(
                "This display server does not let one application see or "
                "close another's windows, so only the applications this "
                "recognised by name could be closed. The guard and the "
                "screen lock are still handled."
            )

        for item in close or []:
            if self._close(item):
                session.closed.append(item.label)
            else:
                session.limits.append(f"{item.label} could not be closed.")

        if self.idle_inhibition_available():
            session.inhibitor_pid = self._start_inhibitor(minutes)
            session.idle_inhibited = session.inhibitor_pid is not None
        else:
            session.limits.append(
                "systemd-inhibit is not available, so the screen will still "
                "blank and the machine will still suspend."
            )

        self._session = session
        return session

    def _start_inhibitor(self, minutes: int) -> int | None:
        """Keep the screen awake and the machine awake for the session."""
        try:
            process = subprocess.Popen(
                [
                    "systemd-inhibit",
                    "--what=idle:sleep",
                    "--why=MentorSmith focus session",
                    "--mode=block",
                    "sleep", str(minutes * 60),
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return process.pid

    def _close(self, item: Distraction) -> bool:
        """Close one distraction. Asks politely before insisting."""
        if item.source == "window" and shutil.which("wmctrl"):
            try:
                subprocess.run(
                    ["wmctrl", "-i", "-c", item.key.split(":", 1)[1]],
                    capture_output=True, timeout=10,
                )
            except (OSError, subprocess.SubprocessError):
                pass
            return True
        if item.pid:
            try:
                os.kill(item.pid, signal.SIGTERM)
                return True
            except (OSError, ProcessLookupError):
                return False
        return False

    def end(self) -> FocusSession | None:
        """End the session and put everything back."""
        session = self._session
        self._session = None
        if session and session.inhibitor_pid:
            try:
                os.kill(session.inhibitor_pid, signal.SIGTERM)
            except (OSError, ProcessLookupError):
                pass
            session.inhibitor_pid = None
        return session

    @property
    def session(self) -> FocusSession | None:
        return self._session

    @property
    def running(self) -> bool:
        return self._session is not None and not self._session.finished


# ── helpers ────────────────────────────────────────────────────────────


def _is_x11() -> bool:
    return bool(os.environ.get("DISPLAY")) and not _is_wayland()


def _is_wayland() -> bool:
    return bool(os.environ.get("WAYLAND_DISPLAY"))


def _friendly_name(program: str) -> str:
    """A readable name for a program, using the known list where it fits."""
    name = Path(program.strip()).name
    return KNOWN_DISTRACTIONS.get(name, name)


#: Program names that are never distractions, however they are titled.
NOT_DISTRACTIONS = (
    "mentorsmith", "xterm", "gnome-terminal", "konsole", "alacritty", "kitty",
    "foot", "code", "codium", "gedit", "kate", "nautilus", "thunar",
    "dolphin", "pcmanfm", "firefox-developer-edition", "crashreporter",
)


def _is_distracting(program: str, label: str) -> bool:
    """Whether a window is plausibly a distraction.

    Deliberately conservative: closing something the learner needed would
    be worse than leaving a tab open.
    """
    name = Path(program.strip()).name.lower()
    if name in NOT_DISTRACTIONS:
        return False
    if name in KNOWN_DISTRACTIONS:
        return True
    # An unknown program with a browser-ish or chat-ish name.
    hints = ("chrome", "firefox", "discord", "telegram", "slack", "steam",
             "spotify", "vlc", "mpv", "zoom", "teams", "opera", "brave")
    return any(hint in name for hint in hints)


def format_duration(minutes: int) -> str:
    """A human way to say how long a session lasts."""
    minutes = max(1, int(minutes))
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''}"
    hours, rest = divmod(minutes, 60)
    if not rest:
        return f"{hours} hour{'s' if hours != 1 else ''}"
    return f"{hours} hour{'s' if hours != 1 else ''} and {rest} minutes"
