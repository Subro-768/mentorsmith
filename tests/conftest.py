"""Shared fixtures.

Tests never touch the user's real database or real AI account:

* the database is always an in-memory or temporary-file SQLite database
* the AI provider is always a fake that returns scripted text or raises a
  scripted error, so the suite runs offline and costs nothing
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make the package importable when running from a checkout.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mentorsmith.compiler.toolchain import Toolchain  # noqa: E402
from mentorsmith.core.db import Database  # noqa: E402
from mentorsmith.providers.base import (  # noqa: E402
    CompletionRequest,
    CompletionResponse,
    LLMProvider,
)


@pytest.fixture()
def database() -> Database:
    """A fresh in-memory database with the schema applied."""
    db = Database(":memory:")
    db.connect()
    yield db
    db.close()


@pytest.fixture()
def temp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "progress.db"


@pytest.fixture(scope="session")
def compiler_available() -> bool:
    """Whether a C++ compiler exists on this machine."""
    return Toolchain().detect().available


@pytest.fixture()
def toolchain(tmp_path: Path) -> Toolchain:
    """A toolchain writing into a throwaway working directory."""
    return Toolchain(work_dir=tmp_path / "workdir", compile_timeout=30, run_timeout=5)


class FakeProvider(LLMProvider):
    """Scripted provider used instead of any real network call."""

    name = "fake"

    def __init__(self, reply: str = "", error: Exception | None = None) -> None:
        self.reply = reply
        self.error = error
        self.requests: list[CompletionRequest] = []

    def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.requests.append(request)
        if self.error is not None:
            raise self.error
        return CompletionResponse(
            text=self.reply,
            model="fake-model",
            provider=self.name,
            raw={"fake": True},
        )

    def describe(self) -> str:
        return "FakeProvider (tests only, no network)"

    @property
    def configured(self) -> bool:
        return True


@pytest.fixture()
def fake_provider() -> FakeProvider:
    return FakeProvider()