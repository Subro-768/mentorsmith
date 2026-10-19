"""Language registry: the one place that knows which languages exist.

Everything keyed by language — curriculum, progress, exercises, sync — uses the
ids in :data:`LANGUAGES`. Adding a language means adding an adapter and a data
file here; see ``docs/adding-a-language.md``.
"""

from __future__ import annotations

from pathlib import Path

from .base import (
    LanguageAdapter,
    ProcessHandle,
    ProcessResult,
    RunSpec,
    ToolInfo,
    ToolMissingError,
    find_tool,
    limit_resources,
    start,
    tool_version,
    truncate,
)
from .c import CAdapter
from .compiled import CompiledAdapter
from .cpp import CppAdapter
from .interpreted import InterpretedAdapter
from .java import JavaAdapter
from .javascript import JavaScriptAdapter
from .python import PythonAdapter

#: Canonical order used everywhere a language list is shown.
LANGUAGE_IDS: tuple[str, ...] = ("cpp", "python", "java", "c", "javascript")

#: Display metadata, kept here so the UI never hardcodes names.
LANGUAGE_LABELS: dict[str, str] = {
    "cpp": "C++",
    "python": "Python",
    "java": "Java",
    "c": "C",
    "javascript": "JavaScript",
}

_ADAPTERS: dict[str, type[LanguageAdapter]] = {
    "cpp": CppAdapter,
    "python": PythonAdapter,
    "java": JavaAdapter,
    "c": CAdapter,
    "javascript": JavaScriptAdapter,
}


def display_name(language_id: str) -> str:
    return LANGUAGE_LABELS.get(language_id, language_id.title())


def adapter_class(language_id: str) -> type[LanguageAdapter]:
    """Adapter class for a language id."""
    try:
        return _ADAPTERS[language_id]
    except KeyError:
        raise KeyError(
            f"Unknown language '{language_id}'. Known: {', '.join(LANGUAGE_IDS)}"
        ) from None


def adapter(language_id: str, work_dir: Path, *, sandbox: bool = False) -> LanguageAdapter:
    """Build an adapter instance writing into ``work_dir``."""
    return adapter_class(language_id)(Path(work_dir), sandbox=sandbox)


def known(language_id: str) -> bool:
    return language_id in _ADAPTERS


def detect(language_id: str, refresh: bool = False) -> ToolInfo:
    """What is installed for a language, without raising."""
    return adapter_class(language_id)(Path(".")).detect(refresh=refresh)


def detect_all() -> dict[str, ToolInfo]:
    """Detect every language, for the settings and status screens."""
    return {language_id: detect(language_id) for language_id in LANGUAGE_IDS}


def curriculum_path(language_id: str) -> Path:
    """Data file holding the curriculum for a language."""
    return (
        Path(__file__).resolve().parent.parent
        / "data"
        / "curriculum"
        / f"{language_id}.json"
    )


def summary() -> dict[str, str]:
    """One line per language, for the settings screen and ``--check``."""
    return {
        language_id: detect(language_id).describe()
        for language_id in LANGUAGE_IDS
    }


__all__ = [
    "LANGUAGE_IDS",
    "LANGUAGE_LABELS",
    "CompiledAdapter",
    "InterpretedAdapter",
    "LanguageAdapter",
    "ProcessHandle",
    "ProcessResult",
    "RunSpec",
    "ToolInfo",
    "ToolMissingError",
    "adapter",
    "adapter_class",
    "curriculum_path",
    "detect",
    "detect_all",
    "display_name",
    "known",
    "start",
    "summary",
]