"""The MentorSmith logo: source, rendering and wiring.

The SVG is the single source of truth. These tests check it stays the source of
truth, that the rendered PNGs exist at the sizes each platform needs, and that
loading the icon can never stop the application starting.

The last one matters most: a missing or corrupt icon is a cosmetic problem, and
``app_icon()`` must degrade to a themed icon rather than raise.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip("PyQt6")

from PyQt6.QtGui import QIcon, QImage  # noqa: E402

from mentorsmith.app import ICON_DIR, ICON_SIZES, app_icon  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SVG = ROOT / "mentorsmith" / "assets" / "logo.svg"


@pytest.fixture(scope="module")
def qt_app():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PyQt6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app


# ======================================================================
# The source
# ======================================================================
class TestLogoSource:
    def test_the_svg_exists(self) -> None:
        assert SVG.exists(), "logo.svg is the source of truth"

    def test_the_svg_is_parseable(self) -> None:
        from PyQt6.QtSvg import QSvgRenderer

        renderer = QSvgRenderer(str(SVG))
        assert renderer.isValid(), (
            "Qt cannot parse the SVG. A common cause is an XML comment inside an "
            "attribute value, which is not legal."
        )

    def test_it_parses_as_xml_too(self) -> None:
        """Qt is lenient about some things; a strict parser is not."""
        import xml.etree.ElementTree as ET

        ET.parse(SVG)   # raises on malformed XML

    def test_it_declares_a_square_viewbox(self) -> None:
        import xml.etree.ElementTree as ET

        root = ET.parse(SVG).getroot()
        assert root.get("viewBox") == "0 0 512 512"

    def test_it_has_no_external_references(self) -> None:
        """An icon must render offline and in an APK, with no external assets."""
        text = SVG.read_text(encoding="utf-8")
        for forbidden in ("http://", "https://", "xlink:href", "<image"):
            if "schemas.android.com" in forbidden:
                continue
            assert forbidden not in text.replace(
                "http://www.w3.org/2000/svg", ""
            ), f"the logo references {forbidden}"


# ======================================================================
# The rendered PNGs
# ======================================================================
class TestRenderedIcons:
    @pytest.mark.parametrize("size", ICON_SIZES)
    def test_every_desktop_size_exists(self, size: int) -> None:
        assert (ICON_DIR / f"mentorsmith-{size}.png").exists(), (
            f"missing mentorsmith-{size}.png; run tools/build_icons.py"
        )

    @pytest.mark.parametrize("size", ICON_SIZES)
    def test_each_png_is_a_real_image_of_the_right_size(self, size: int) -> None:
        image = QImage(str(ICON_DIR / f"mentorsmith-{size}.png"))
        assert not image.isNull(), f"mentorsmith-{size}.png is not a readable PNG"
        assert image.width() == size
        assert image.height() == size

    @pytest.mark.parametrize("size", (16, 32, 64))
    def test_small_icons_are_legible_not_blank(self, size: int) -> None:
        """A tiny icon that renders as one flat colour is useless."""
        image = QImage(str(ICON_DIR / f"mentorsmith-{size}.png"))
        colours = {image.pixel(x, y) for x in range(size) for y in range(size)}
        assert len(colours) >= 4, (
            f"the {size}px icon has too few distinct colours; it is probably blank"
        )

    def test_the_centre_is_opaque(self, qt_app) -> None:
        """The plate supplies the background; the middle must be solid."""
        image = QImage(str(ICON_DIR / "mentorsmith-256.png"))
        assert image.pixelColor(128, 128).alpha() > 0, "the plate is missing"

    def test_the_corners_are_transparent(self, qt_app) -> None:
        """The plate is a rounded square, so the very corners must be clear.

        This is deliberate: a square icon looks wrong under a rounded launcher
        or panel mask.
        """
        image = QImage(str(ICON_DIR / "mentorsmith-256.png"))
        assert image.pixelColor(2, 2).alpha() == 0, "the plate corner is not rounded"


class TestAndroidIcons:
    @pytest.mark.parametrize(
        "folder,size",
        [
            ("mipmap-mdpi", 48), ("mipmap-hdpi", 72), ("mipmap-xhdpi", 96),
            ("mipmap-xxhdpi", 144), ("mipmap-xxxhdpi", 192),
        ],
    )
    def test_android_density_buckets_exist(self, folder: str, size: int) -> None:
        path = ROOT / "android" / "app" / "src" / "main" / "res" / folder / "ic_launcher.png"
        assert path.exists(), f"missing {folder}/ic_launcher.png"
        image = QImage(str(path))
        assert image.width() == size

    def test_the_adaptive_icon_defines_all_three_layers(self) -> None:
        path = (
            ROOT / "android" / "app" / "src" / "main" / "res"
            / "mipmap-anydpi-v26" / "ic_launcher.xml"
        )
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        for layer in ("background", "foreground", "monochrome"):
            assert f"<{layer}" in text, f"adaptive icon has no {layer} layer"

    def test_the_manifest_points_at_the_mipmaps(self) -> None:
        manifest = (
            ROOT / "android" / "app" / "src" / "main" / "AndroidManifest.xml"
        ).read_text(encoding="utf-8")
        assert "@mipmap/ic_launcher" in manifest

    def test_the_stale_vector_drawable_is_gone(self) -> None:
        """It would shadow the real icon and silently win on older devices."""
        stale = ROOT / "android" / "app" / "src" / "main" / "res" / "drawable" / "ic_launcher.xml"
        assert not stale.exists(), (
            "an unreferenced ic_launcher.xml is left in res/drawable"
        )


# ======================================================================
# Loading
# ======================================================================
class TestIconLoading:
    def test_the_icon_loads(self, qt_app) -> None:
        assert not app_icon().isNull()

    def test_the_icon_carries_every_size(self, qt_app) -> None:
        icon = app_icon()
        for size in (16, 32, 256):
            assert not icon.pixmap(size, size).isNull(), f"no {size}px variant"

    def test_a_missing_icon_directory_does_not_raise(
        self, qt_app, monkeypatch, tmp_path
    ) -> None:
        """Cosmetic problem must never stop the app starting."""
        import mentorsmith.app as app_module

        monkeypatch.setattr(app_module, "ICON_DIR", tmp_path / "does-not-exist")
        icon = app_module.app_icon()
        # Either a themed fallback or an empty icon; never an exception.
        assert isinstance(icon, QIcon)

    def test_corrupt_pngs_do_not_raise(self, qt_app, monkeypatch, tmp_path) -> None:
        import mentorsmith.app as app_module

        fake = tmp_path / "icons"
        fake.mkdir()
        for size in ICON_SIZES:
            (fake / f"mentorsmith-{size}.png").write_bytes(b"not a png at all")
        monkeypatch.setattr(app_module, "ICON_DIR", fake)
        assert isinstance(app_module.app_icon(), QIcon)

    def test_create_application_sets_the_desktop_file_name(self) -> None:
        """Without it the .desktop entry cannot launch the app.

        Asserted against the source rather than a live QApplication: Qt permits
        only one per process, and the module-scoped fixture owns it here.
        """
        source = (ROOT / "mentorsmith" / "app.py").read_text(encoding="utf-8")
        assert 'setDesktopFileName("mentorsmith")' in source


# ======================================================================
# The .desktop entry
# ======================================================================
class TestDesktopEntry:
    @pytest.fixture()
    def entry(self) -> str:
        path = ROOT / "mentorsmith.desktop"
        assert path.exists(), "mentorsmith.desktop is missing"
        return path.read_text(encoding="utf-8")

    def test_it_declares_the_required_keys(self, entry: str) -> None:
        for key in ("[Desktop Entry]", "Type=Application", "Name=", "Exec=", "Icon="):
            assert key in entry, f"{key} missing from the .desktop file"

    def test_it_uses_the_brand_icon(self, entry: str) -> None:
        assert "Icon=mentorsmith" in entry

    def test_it_points_at_main(self, entry: str) -> None:
        assert "main.py" in entry

    def test_it_is_in_the_right_categories(self, entry: str) -> None:
        assert "Education" in entry or "Development" in entry

# ======================================================================
# The Exec line must actually resolve.
#
# The first version shipped `Exec=python3 %k/../main.py`. %k is the directory
# holding the .desktop file, so that expanded to ~/.local/share/main.py - a
# path that does not exist. The menu entry simply did nothing when clicked,
# and nothing in the test suite noticed.
# ======================================================================
class TestDesktopEntryIsLaunchable:
    @pytest.fixture()
    def entry(self) -> dict[str, str]:
        """Parse the .desktop file into key -> value."""
        text = (ROOT / "mentorsmith.desktop").read_text(encoding="utf-8")
        values: dict[str, str] = {}
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith(("[", "#")):
                continue
            key, sep, value = line.partition("=")
            if sep:
                values[key.strip()] = value.strip()
        return values

    def test_the_exec_command_resolves_to_a_real_binary(self, entry) -> None:
        import shutil

        command = entry["Exec"].split()[0]
        assert not command.startswith("%"), (
            "Exec must not start with a field code; it would expand to a path "
            "that does not exist"
        )
        assert shutil.which(command) or (ROOT / command).exists(), (
            f"Exec={command!r} does not resolve to anything runnable"
        )

    def test_the_exec_does_not_use_percent_k_as_a_directory_hint(self, entry) -> None:
        """%k is the .desktop file's own directory, never the source checkout."""
        assert "%k" not in entry["Exec"], (
            "Exec uses %k, which expands to ~/.local/share, not the repo"
        )

    def test_the_path_key_is_absent_or_absolute(self, entry) -> None:
        """An empty Path= is a validation warning and serves no purpose."""
        path = entry.get("Path")
        assert not path or path.startswith("/"), f"Path={path!r} is not usable"

    def test_a_single_main_category(self, entry) -> None:
        """More than one main category makes the app appear twice in the menu."""
        # "Education;" is one category plus a terminator. A second main
        # category would make the app appear twice in the menu.
        categories = [c for c in entry["Categories"].split(";") if c]
        assert len(categories) == 1, (
            f"only the first category is a main one; found {categories}"
        )

    def test_the_keyword_string_carries_the_extra_terms(self, entry) -> None:
        keywords = entry.get("Keywords", "").lower()
        for term in ("python", "java", "tutor"):
            assert term in keywords

    def test_the_launcher_script_is_importable_and_runnable(self) -> None:
        """The installed launcher imports the package from the checkout."""
        import subprocess

        launcher = ROOT / "tools" / "install_desktop.py"
        assert launcher.exists()
        result = subprocess.run(
            [sys.executable, str(launcher), "--dry-run"],
            capture_output=True, text=True, timeout=120, cwd=str(ROOT),
        )
        assert result.returncode == 0, result.stderr
        assert "mentorsmith" in result.stdout

    def test_the_installer_has_an_uninstall_path(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROOT / "tools" / "install_desktop.py"),
             "--uninstall", "--dry-run"],
            capture_output=True, text=True, timeout=120, cwd=str(ROOT),
        )
        assert result.returncode == 0, result.stderr
        assert "would remove" in result.stdout


# ======================================================================
# Why the installer is shaped the way it is.
#
# Two rounds of breakage, both invisible:
#
#   1. It installed icons into the shared hicolor tree and wrote an
#      index.theme listing only the directories it had created. Every icon
#      in a directory it did not list became invisible - a GNOME extension,
#      another app - with nothing on disk changed to show why.
#   2. It ran `gtk-update-icon-cache -f` against that same shared tree,
#      rewriting a cache every other icon on the machine depends on.
#
# The fix is structural rather than defensive: the icons now live in a
# directory this app owns outright, and the desktop entry references them by
# absolute path, so no theme index is needed and no shared cache is touched.
#
# The tests below plant a whole foreign icon tree, install, and assert that
# not one file outside our own directory changed.
# ======================================================================
class TestInstallerWritesOnlyItsOwnDirectory:
    @pytest.fixture()
    def world(self, tmp_path, monkeypatch):
        """A fake HOME containing somebody else's icons and a desktop cache."""
        import importlib

        fake_home = tmp_path / "home"
        hicolor = fake_home / ".local" / "share" / "icons" / "hicolor"

        # Another app's icons, in directories of every kind.
        for rel in ("scalable/apps", "24x24/apps", "256x256/apps"):
            (hicolor / rel).mkdir(parents=True)
        (hicolor / "scalable" / "apps" / "org.example.Extension.svg").write_text(
            "<svg/>", encoding="utf-8"
        )
        (hicolor / "256x256" / "apps" / "otherapp.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        (hicolor / "index.theme").write_text(
            "[Icon Theme]\nName=Hicolor\nComment=Not ours\n"
            "Directories=scalable/apps,24x24/apps,256x256/apps\n",
            encoding="utf-8",
        )

        # Another app's desktop entry, plus the shared desktop cache.
        apps = fake_home / ".local" / "share" / "applications"
        apps.mkdir(parents=True)
        (apps / "otherapp.desktop").write_text("[Desktop Entry]\n", encoding="utf-8")
        (apps / "mimeinfo.cache").write_bytes(b"shared cache")

        snapshot = {
            str(f): (f.stat().st_mtime_ns, f.read_bytes())
            for f in fake_home.rglob("*") if f.is_file()
        }

        monkeypatch.setenv("HOME", str(fake_home))
        sys.path.insert(0, str(ROOT / "tools"))
        installer = importlib.reload(importlib.import_module("install_desktop"))
        installer.HOME = fake_home
        installer.BIN_DIR = fake_home / ".local" / "bin"
        installer.APPS_DIR = apps
        installer.ICONS_ROOT = fake_home / ".local" / "share" / "icons" / "mentorsmith"

        return installer, fake_home, snapshot, hicolor, apps

    def test_icons_go_to_a_directory_we_own(self, world) -> None:
        installer, _home, _snap, _hicolor, _apps = world
        assert installer.install() == 0
        assert installer.ICONS_ROOT.name == "mentorsmith"
        assert installer.ICONS_ROOT.parent.name == "icons"
        assert installer.ICONS_ROOT.exists()
        assert list(installer.ICONS_ROOT.rglob("mentorsmith.png")), "no icons installed"

    def test_nothing_outside_our_directory_is_written(self, world) -> None:
        """The core property: the only files that appear are ours."""
        installer, home, snapshot, _hicolor, _apps = world
        assert installer.install() == 0

        after = {
            str(f): (f.stat().st_mtime_ns, f.read_bytes())
            for f in home.rglob("*") if f.is_file()
        }
        touched = {
            p for p in set(snapshot) | set(after)
            if snapshot.get(p) != after.get(p)
        }
        allowed_roots = (
            str(installer.ICONS_ROOT),
            str(installer.BIN_DIR),
        )
        allowed_files = {str(installer.APPS_DIR / "mentorsmith.desktop")}
        for path in touched:
            assert path in allowed_files or path.startswith(allowed_roots), (
                f"the installer modified {path}, which it does not own"
            )

    def test_the_shared_index_theme_is_untouched(self, world) -> None:
        installer, _home, _snap, hicolor, _apps = world
        assert installer.install() == 0
        index = hicolor / "index.theme"
        assert index.exists(), "the installer deleted somebody else's index.theme"
        assert "Not ours" in index.read_text(encoding="utf-8")

    def test_foreign_icons_survive(self, world) -> None:
        installer, _home, _snap, hicolor, _apps = world
        assert installer.install() == 0
        assert (hicolor / "scalable" / "apps" / "org.example.Extension.svg").exists()
        assert (hicolor / "256x256" / "apps" / "otherapp.png").exists()

    def test_no_icon_is_written_into_hicolor(self, world) -> None:
        installer, _home, _snap, hicolor, _apps = world
        assert installer.install() == 0
        assert not list(hicolor.rglob("mentorsmith.png")), (
            "icons must not be installed into the shared tree"
        )

    def test_the_shared_desktop_cache_is_not_rewritten(self, world) -> None:
        """update-desktop-database rewrites mimeinfo.cache, which every other
        per-user application shares. Off unless --refresh-caches is passed."""
        installer, _home, _snap, _hicolor, apps = world
        cache = apps / "mimeinfo.cache"
        before = cache.read_bytes()
        assert installer.install() == 0
        assert cache.read_bytes() == before

    def test_another_apps_desktop_entry_survives(self, world) -> None:
        installer, _home, _snap, _hicolor, apps = world
        assert installer.install() == 0
        assert (apps / "otherapp.desktop").exists()

    def test_uninstall_restores_the_original_world(self, world) -> None:
        """Not a single trace left, and nothing of anyone else's gone."""
        installer, home, snapshot, _hicolor, _apps = world
        assert installer.install() == 0
        assert installer.uninstall() == 0

        after = {
            str(f): (f.stat().st_mtime_ns, f.read_bytes())
            for f in home.rglob("*") if f.is_file()
        }
        # Everything that was there before is still there, unchanged...
        for path, state in snapshot.items():
            assert path in after, f"uninstall removed {path}"
            assert after[path] == state, f"uninstall modified {path}"
        # ...and everything that appeared is ours, and is now gone.
        for path in set(after) - set(snapshot):
            assert path.startswith(str(installer.ICONS_ROOT)), (
                f"uninstall left behind {path}"
            )


# ======================================================================
# The installed desktop entry has to actually work
# ======================================================================
class TestInstalledEntryWorks:
    @pytest.fixture()
    def installed(self, tmp_path, monkeypatch):
        import importlib

        fake_home = tmp_path / "home"
        (fake_home / ".local" / "share").mkdir(parents=True)
        monkeypatch.setenv("HOME", str(fake_home))

        sys.path.insert(0, str(ROOT / "tools"))
        installer = importlib.reload(importlib.import_module("install_desktop"))
        installer.HOME = fake_home
        installer.BIN_DIR = fake_home / ".local" / "bin"
        installer.APPS_DIR = fake_home / ".local" / "share" / "applications"
        installer.ICONS_ROOT = fake_home / ".local" / "share" / "icons" / "mentorsmith"

        assert installer.install() == 0
        return installer

    def test_the_icon_line_points_at_a_file_that_exists(self, installed) -> None:
        """An Icon= that points nowhere fails silently."""
        text = (installed.APPS_DIR / "mentorsmith.desktop").read_text(encoding="utf-8")
        value = next(
            line for line in text.splitlines() if line.startswith("Icon=")
        ).split("=", 1)[1].strip()
        assert value.startswith("/"), f"Icon={value!r} is a theme name"
        assert Path(value).exists(), f"Icon={value!r} does not exist"

    def test_the_icon_line_points_inside_our_own_directory(self, installed) -> None:
        text = (installed.APPS_DIR / "mentorsmith.desktop").read_text(encoding="utf-8")
        value = next(
            line for line in text.splitlines() if line.startswith("Icon=")
        ).split("=", 1)[1].strip()
        assert str(installed.ICONS_ROOT) in value, (
            "the icon must live in a directory this app owns"
        )

    def test_every_installed_size_is_present(self, installed) -> None:
        for size in (16, 48, 256, 512):
            path = installed.ICONS_ROOT / f"{size}x{size}" / "mentorsmith.png"
            assert path.exists(), f"{path} missing"

    def test_the_exec_resolves_to_an_executable(self, installed) -> None:
        text = (installed.APPS_DIR / "mentorsmith.desktop").read_text(encoding="utf-8")
        binary = next(
            line for line in text.splitlines() if line.startswith("Exec=")
        ).split("=", 1)[1].strip()
        launcher = installed.BIN_DIR / binary
        assert launcher.exists(), f"Exec={binary!r} does not exist"
        assert launcher.stat().st_mode & 0o111, "not executable"

    def test_the_launcher_points_at_this_checkout(self, installed) -> None:
        """So editing the source and re-running takes effect with no reinstall."""
        launcher = installed.BIN_DIR / "mentorsmith"
        assert str(ROOT) in launcher.read_text(encoding="utf-8")

    def test_no_index_theme_is_written_anywhere(self, installed) -> None:
        """We reference the PNG by absolute path; a theme index is unnecessary,
        and writing one into a shared tree is what broke the user's icons."""
        assert not list(installed.HOME.rglob("index.theme")), (
            "the installer wrote an icon theme index it has no business writing"
        )

    def test_installing_twice_is_idempotent(self, installed) -> None:
        icons = sorted(installed.ICONS_ROOT.rglob("mentorsmith.png"))
        assert installed.install() == 0
        assert sorted(installed.ICONS_ROOT.rglob("mentorsmith.png")) == icons
