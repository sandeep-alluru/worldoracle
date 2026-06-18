"""Shared pytest fixtures for worldoracle tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def tmp_db(tmp_path: pytest.TempPathFactory) -> str:
    """Return a path to a temporary SQLite database."""
    return str(tmp_path / "test.db")


@pytest.fixture
def sample_predicate():  # type: ignore[return]
    """Return a sample WorldPredicate for reuse across tests."""
    from worldoracle.predicate import WorldPredicate

    return WorldPredicate(
        subject="king",
        attribute="alive",
        value=True,
        source="observation",
        confidence=0.9,
        timestamp=100.0,
    )
