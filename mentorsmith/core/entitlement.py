"""Entitlement: the free stretch, and the licence that ends it.

What this is for
----------------
The product is free for a first stretch - long enough for a learner to get
hooked - and paid after that. This module is the app side of that: it
knows when the free stretch began, when it ends, and whether a licence key
has been entered that says otherwise.

How a licence is checked
------------------------
A licence key is a payload and a signature over it::

    MS1.<base64url(payload)>.<base64url(signature)>

The signature is RSA-2048 with PKCS#1 v1.5 over SHA-256. The app holds
**only the public key**, so it can check a licence and cannot mint one. The
private key is not in this repository and is not on the machine the app
runs on; it lives with whoever issues the licences.

Why RSA and not a shared secret
-------------------------------
A shared secret has to be in the app, and anything in the app can be
extracted - a student who unpacked the binary could then write themselves
a licence. Verification with a *public* key cannot be forged that way: the
private half never reaches the machine.

The verification is hand-written because `cryptography` is not a dependency
and this project does not want one for this. That is safe here, and it is
worth being precise about why: **verification** is the easy direction.
It is a modular exponentiation and a comparison. Signing - the part that
needs the private key - happens in a separate tool that is not shipped.

What is gated
-------------
The gate is **off by default**. A setting turns it on. That is deliberate:
the free stretch is the learner's to have, and a gate that appears without
warning is how an app earns a bad name. When the gate is on and the free
stretch has run out, the paid features stop working and the app says
exactly why, and how to fix it.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timedelta, timezone

#: The public key lives in a data file, not in this module, so it can be
#: replaced without touching code and so nobody has to retype 600 digits.
_PUBLIC_KEY_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "licence_public_key.json"
)

#: How long the free stretch lasts, in days.
DEFAULT_TRIAL_DAYS = 30

#: The prefix every licence key carries.
LICENCE_PREFIX = "MS1"

#: SHA-256's DigestInfo prefix, as PKCS#1 v1.5 requires.
_SHA256_DIGEST_INFO = bytes.fromhex("3031300d060960864801650304020105000420")


class EntitlementError(RuntimeError):
    """The licence or the entitlement state is not usable."""


# ── RSA verification ───────────────────────────────────────────────────


def _b64url_decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _public_key() -> tuple[int, int]:
    """The modulus and exponent of the licence signing key."""
    try:
        raw = json.loads(_PUBLIC_KEY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return (0, 0)
    return int(raw.get("modulus", 0)), int(raw.get("exponent", 0))


def verify_signature(payload: bytes, signature: bytes) -> bool:
    """Check an RSA-2048 PKCS#1 v1.5 signature over SHA-256.

    This is the *verification* direction: a public-key operation and a
    comparison. There is no secret here to get wrong, which is why it is
    safe to write out longhand rather than take a dependency for.
    """
    modulus, exponent = _public_key()
    if not modulus:
        return False
    key_bytes = (modulus.bit_length() + 7) // 8
    if len(signature) != key_bytes:
        return False
    value = int.from_bytes(signature, "big")
    if value >= modulus:
        return False
    decoded = pow(value, exponent, modulus).to_bytes(key_bytes, "big")

    expected = _SHA256_DIGEST_INFO + hashlib.sha256(payload).digest()
    # 0x00 0x01 0xFF... 0x00 DigestInfo
    padding_length = key_bytes - len(expected) - 3
    if padding_length < 8:
        return False
    wanted = b"\x00\x01" + b"\xff" * padding_length + b"\x00" + expected
    return decoded == wanted


# ── Licence keys ───────────────────────────────────────────────────────


@dataclass
class Licence:
    """A licence that has been checked and found good."""

    name: str = ""
    tier: str = "pro"
    expires: str = ""
    key: str = ""

    @property
    def expired(self) -> bool:
        if not self.expires:
            return False
        try:
            until = datetime.fromisoformat(self.expires)
        except ValueError:
            return True
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
        return until < datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "tier": self.tier,
            "expires": self.expires,
        }


def check_licence(key: str) -> Licence:
    """Check a licence key. Raises :class:`EntitlementError` if it is not good.

    A bad key is a wrong key, not a broken app: the message says what was
    wrong with it.
    """
    text = (key or "").strip()
    if not text:
        raise EntitlementError("No licence key was entered.")
    parts = text.split(".")
    if len(parts) != 3 or parts[0] != LICENCE_PREFIX:
        raise EntitlementError(
            "That is not a MentorSmith licence key. It should look like "
            f"{LICENCE_PREFIX}.<code>.<signature>."
        )
    try:
        payload_raw = _b64url_decode(parts[1])
        signature = _b64url_decode(parts[2])
    except Exception:
        raise EntitlementError("That licence key is damaged.") from None

    if not verify_signature(payload_raw, signature):
        raise EntitlementError(
            "That licence key is not valid. Check it was copied whole, "
            "including the signature at the end."
        )

    try:
        payload = json.loads(payload_raw.decode("utf-8"))
    except Exception:
        raise EntitlementError("That licence key is damaged.") from None

    licence = Licence(
        name=str(payload.get("name", "")),
        tier=str(payload.get("tier", "pro")),
        expires=str(payload.get("expires", "")),
        key=text,
    )
    if licence.expired:
        raise EntitlementError(
            f"That licence expired on {licence.expires[:10]}."
        )
    return licence


# ── The entitlement itself ─────────────────────────────────────────────


@dataclass
class Entitlement:
    """What the app is allowed to do right now."""

    #: True when the paid features should work.
    pro: bool = False
    #: True when the free stretch is still running.
    in_trial: bool = False
    trial_started: str = ""
    trial_ends: str = ""
    days_left: int = 0
    #: The licence, when there is one.
    licence: Licence | None = None
    #: Why the app is in this state, in words for the learner.
    reason: str = ""
    #: Whether the gate is switched on at all.
    gate_enabled: bool = False

    @property
    def trial_over(self) -> bool:
        return not self.in_trial and self.licence is None

    def to_dict(self) -> dict:
        return {
            "pro": self.pro,
            "in_trial": self.in_trial,
            "trial_started": self.trial_started,
            "trial_ends": self.trial_ends,
            "days_left": self.days_left,
            "licence": self.licence.to_dict() if self.licence else None,
            "reason": self.reason,
            "gate_enabled": self.gate_enabled,
        }


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(stamp: str) -> datetime | None:
    if not stamp:
        return None
    try:
        parsed = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def entitlement(
    settings: dict,
    *,
    trial_days: int = DEFAULT_TRIAL_DAYS,
) -> Entitlement:
    """Work out what the app may do, from the settings.

    The rules, in order:

    1. A valid licence means everything works.
    2. Otherwise, if the free stretch has not run out, everything works.
    3. Otherwise the paid features stop - but only if the gate is on.
    """
    state = Entitlement()

    state.gate_enabled = bool(settings.get("licence_gate_enabled", False))

    # 1. A licence.
    key = str(settings.get("licence_key", "") or "")
    if key:
        try:
            state.licence = check_licence(key)
        except EntitlementError:
            state.licence = None
    if state.licence is not None:
        state.pro = True
        state.reason = (
            f"Licensed to {state.licence.name}."
            if state.licence.name
            else "Licensed."
        )
        return state

    # 2. The free stretch.
    started = str(settings.get("trial_started", "") or "")
    if not started:
        started = _now().isoformat(timespec="seconds")
        settings["trial_started"] = started
    state.trial_started = started
    begin = _parse(started) or _now()
    end = begin + timedelta(days=max(0, int(trial_days)))
    state.trial_ends = end.isoformat(timespec="seconds")
    remaining = (end - _now()).total_seconds() / 86400.0
    state.days_left = max(0, int(remaining + 0.999))

    if remaining > 0:
        state.in_trial = True
        state.pro = True
        state.reason = (
            f"Your first {trial_days} days are free. "
            f"{state.days_left} day{'s' if state.days_left != 1 else ''} left."
        )
        return state

    # 3. Over.
    state.in_trial = False
    state.pro = False
    state.reason = (
        "Your free stretch has ended. Enter a licence key to carry on, or "
        "keep what you have - your progress is still saved."
    )
    return state


def activate_licence(settings: dict, key: str) -> Licence:
    """Check a key and store it. Raises if the key is not good."""
    licence = check_licence(key)
    settings["licence_key"] = licence.key
    return licence


def clear_licence(settings: dict) -> None:
    """Forget the licence. Used when the learner wants to try the free
    stretch again on another machine."""
    settings.pop("licence_key", None)


_LICENCE_KEY_RE = re.compile(r"^MS1\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")


def looks_like_a_licence(key: str) -> bool:
    """Whether a string is shaped like a licence key, for the input field."""
    return bool(_LICENCE_KEY_RE.match((key or "").strip()))
