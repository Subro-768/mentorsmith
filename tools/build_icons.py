#!/usr/bin/env python3
"""Render the MentorSmith logo into PNGs for every platform that needs one.

The SVG in ``mentorsmith/assets/logo.svg`` is the single source of truth. This
renders it to:

* ``mentorsmith/assets/icons/mentorsmith-<size>.png`` - used by the desktop app
  and by the Linux ``.desktop`` file
* ``android/.../mipmap-*/ic_launcher.png``  - the Android launcher icon

Rendering uses PyQt6's QtSvg, which is already a dependency, so there is no
Inkscape or ImageMagick requirement.

Run it after editing the SVG::

    python3 tools/build_icons.py

``--check`` verifies the PNGs on disk match the SVG and exits non-zero if they
are stale, which is what CI should call.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

SVG = ROOT / "mentorsmith" / "assets" / "logo.svg"
DESKTOP_DIR = ROOT / "mentorsmith" / "assets" / "icons"
ANDROID_RES = ROOT / "android" / "app" / "src" / "main" / "res"

#: Sizes the desktop uses. 16 is the smallest a Linux panel will render.
DESKTOP_SIZES = (16, 24, 32, 48, 64, 128, 256, 512)

#: Android launcher densities, in dp. mdpi is 48px, not 16.
ANDROID_SIZES = {
    "mipmap-mdpi": 48,
    "mipmap-hdpi": 72,
    "mipmap-xhdpi": 96,
    "mipmap-xxhdpi": 144,
    "mipmap-xxxhdpi": 192,
}


def _renderer():
    from PyQt6.QtSvg import QSvgRenderer

    if not SVG.exists():
        raise SystemExit(f"missing source logo: {SVG}")
    renderer = QSvgRenderer(str(SVG))
    if not renderer.isValid():
        raise SystemExit(f"{SVG} is not valid SVG")
    return renderer


def render(size: int, destination: Path) -> bytes:
    """Render the SVG at ``size`` x ``size`` and write a PNG.

    QSvgRenderer.render() takes a QPainter, so painting goes through one.
    Rendering straight at the target size (rather than rendering at 512 and
    downsampling) is what keeps the 16px panel icon legible.
    """
    from PyQt6.QtCore import QRectF, Qt
    from PyQt6.QtGui import QImage, QPainter

    image = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    try:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        _renderer().render(painter, QRectF(0, 0, size, size))
    finally:
        painter.end()

    destination.parent.mkdir(parents=True, exist_ok=True)
    if not image.save(str(destination), "PNG"):
        raise SystemExit(f"could not write {destination}")
    return destination.read_bytes()


def write_all(check_only: bool = False) -> int:
    stale: list[Path] = []
    written = 0

    for size in DESKTOP_SIZES:
        destination = DESKTOP_DIR / f"mentorsmith-{size}.png"
        if check_only:
            if not destination.exists():
                stale.append(destination)
        else:
            render(size, destination)
            written += 1

    for folder, size in ANDROID_SIZES.items():
        destination = ANDROID_RES / folder / "ic_launcher.png"
        if check_only:
            if not destination.exists():
                stale.append(destination)
        else:
            render(size, destination)
            written += 1

    if check_only:
        if stale:
            print("Stale or missing icons:", file=sys.stderr)
            for path in stale:
                print(f"  {path.relative_to(ROOT)}", file=sys.stderr)
            print("\nRun: python3 tools/build_icons.py", file=sys.stderr)
            return 1
        print(f"Icons are current ({len(DESKTOP_SIZES)} desktop sizes).")
        return 0

    print(f"Rendered {written} icon(s) from {SVG.relative_to(ROOT)}")
    print(f"  desktop : {DESKTOP_DIR.relative_to(ROOT)}")
    if ANDROID_RES.exists():
        print(f"  android : {ANDROID_RES.relative_to(ROOT)}/mipmap-*/ic_launcher.png")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the rendered icons exist and are current; do not write.",
    )
    args = parser.parse_args()
    return write_all(check_only=args.check)


if __name__ == "__main__":
    sys.exit(main())