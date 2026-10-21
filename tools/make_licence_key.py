#!/usr/bin/env python3
"""Issue a MentorSmith licence key.

The **private** key never goes in the repository and never goes on the
machine the app runs on. It is needed only here, when a licence is being
written.

    python3 tools/make_licence_key.py --name "A. Learner" --months 6
    python3 tools/make_licence_key.py --regenerate   # new key pair

The key pair lives outside the repository by default:

    ~/.local/share/mentorsmith/licence-signing/

``--regenerate`` writes a new pair and updates the app's public key. It
**invalidates every licence already issued**, so it is not something to do
casually.

The signature is RSA-2048 with PKCS#1 v1.5 over SHA-256, made with the
``openssl`` command line - so this tool needs no Python package either.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

#: Where the key pair lives. Outside the repository, on purpose.
KEY_DIR = Path.home() / ".local/share/mentorsmith/licence-signing"
PRIVATE = KEY_DIR / "private.pem"
PUBLIC = KEY_DIR / "public.pem"
PUBLIC_NUMBERS = KEY_DIR / "public_numbers.txt"
APP_PUBLIC_KEY = ROOT / "mentorsmith" / "data" / "licence_public_key.json"

#: PKCS#1 v1.5 DigestInfo for SHA-256.
SHA256_DIGEST_INFO = bytes.fromhex("3031300d060960864801650304020105000420")


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def generate_key_pair() -> None:
    """Make a new key pair and update the app's public key."""
    KEY_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["openssl", "genrsa", "-out", str(PRIVATE), "2048"],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["openssl", "rsa", "-in", str(PRIVATE), "-pubout", "-out", str(PUBLIC)],
        check=True, capture_output=True,
    )
    PRIVATE.chmod(0o600)

    modulus = subprocess.run(
        ["openssl", "rsa", "-in", str(PRIVATE), "-noout", "-modulus"],
        check=True, capture_output=True, text=True,
    ).stdout.strip().removeprefix("Modulus=")

    n = int(modulus, 16)
    e = 65537
    PUBLIC_NUMBERS.write_text(f"{n}\n{e}\n")

    APP_PUBLIC_KEY.write_text(json.dumps({
        "_comment": (
            "The public half of the licence signing key. The app can check a "
            "licence with this and cannot write one: the private half is not "
            "in this repository and not on the machine the app runs on."
        ),
        "algorithm": "RSASSA-PKCS1-v1_5-SHA256",
        "modulus": str(n),
        "exponent": e,
        "bits": 2048,
    }, indent=1) + "\n")
    print(f"  new key pair written to {KEY_DIR}")
    print(f"  the app's public key updated at {APP_PUBLIC_KEY}")
    print("  Every licence issued with the old key is now invalid.")


def sign(payload: bytes) -> bytes:
    """Sign with the private key, using openssl."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        data = Path(tmp) / "payload.bin"
        signature = Path(tmp) / "payload.sig"
        data.write_bytes(payload)
        subprocess.run(
            [
                "openssl", "dgst", "-sha256", "-sign", str(PRIVATE),
                "-out", str(signature), str(data),
            ],
            check=True, capture_output=True,
        )
        return signature.read_bytes()


def issue(name: str, months: int, tier: str = "pro") -> str:
    """Write a licence key for someone."""
    if not PRIVATE.exists():
        raise SystemExit(
            f"No private key at {PRIVATE}. Run with --regenerate first."
        )
    expires = ""
    if months > 0:
        expires = (
            datetime.now(timezone.utc) + timedelta(days=30 * months)
        ).date().isoformat()
    payload = json.dumps(
        {"name": name, "tier": tier, "expires": expires},
        separators=(",", ":"), sort_keys=True,
    ).encode("utf-8")
    signature = sign(payload)
    return f"MS1.{b64url(payload)}.{b64url(signature)}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", default="", help="Who the licence is for.")
    parser.add_argument(
        "--months", type=int, default=12,
        help="How many months it is valid for. 0 means it never expires.",
    )
    parser.add_argument("--tier", default="pro", help="The tier, usually pro.")
    parser.add_argument(
        "--regenerate", action="store_true",
        help="Make a new key pair. Invalidates every licence already issued.",
    )
    args = parser.parse_args()

    if args.regenerate:
        generate_key_pair()
        return 0

    key = issue(args.name, args.months, args.tier)
    print(key)
    print()
    print("  Check it against the app before handing it over:")
    from mentorsmith.core.entitlement import check_licence

    licence = check_licence(key)
    print(f"    valid · tier {licence.tier} · expires {licence.expires or 'never'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
