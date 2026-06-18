"""Tests for WorldOracleStore."""

from __future__ import annotations

import pytest

from worldoracle.predicate import RepairFrame, WorldPredicate
from worldoracle.store import WorldOracleStore


def test_store_creates_db_file(tmp_db: str) -> None:
    """Store should create a SQLite file at the given path."""
    from pathlib import Path

    store = WorldOracleStore(tmp_db)
    store.close()
    assert Path(tmp_db).exists()


def test_save_and_retrieve_predicate(tmp_db: str) -> None:
    """save_predicate + get_belief_state should round-trip a predicate."""
    store = WorldOracleStore(tmp_db)
    pred = WorldPredicate(
        subject="king", attribute="alive", value=True,
        source="observation", confidence=0.9, timestamp=100.0,
    )
    store.save_predicate("guard-1", pred)
    state = store.get_belief_state("guard-1")
    store.close()
    assert len(state.predicates) == 1
    p = state.predicates[0]
    assert p.subject == "king"
    assert p.attribute == "alive"
    assert p.value is True
    assert p.source == "observation"
    assert p.confidence == pytest.approx(0.9)
    assert p.timestamp == pytest.approx(100.0)


def test_list_npc_ids(tmp_db: str) -> None:
    """list_npc_ids should return unique IDs for all NPCs with predicates."""
    store = WorldOracleStore(tmp_db)
    store.save_predicate("guard-1", WorldPredicate(subject="king", attribute="alive", value=True))
    store.save_predicate("guard-2", WorldPredicate(subject="queen", attribute="alive", value=True))
    ids = store.list_npc_ids()
    store.close()
    assert set(ids) == {"guard-1", "guard-2"}


def test_save_and_get_repair(tmp_db: str) -> None:
    """save_repair + get_repairs should round-trip a repair frame."""
    store = WorldOracleStore(tmp_db)
    repair = RepairFrame(
        predicate_a_id="aaa",
        predicate_b_id="bbb",
        strategy="prefer_newer",
        resolved_value=True,
        reason="test repair",
        timestamp=0.0,
    )
    store.save_repair(repair)
    repairs = store.get_repairs()
    store.close()
    assert len(repairs) == 1
    r = repairs[0]
    assert r.strategy == "prefer_newer"
    assert r.resolved_value is True
    assert r.reason == "test repair"


def test_multiple_npcs_stored_separately(tmp_db: str) -> None:
    """Predicates for different NPCs should not bleed into each other."""
    store = WorldOracleStore(tmp_db)
    store.save_predicate("guard-1", WorldPredicate(subject="king", attribute="alive", value=True))
    store.save_predicate(
        "guard-2",
        WorldPredicate(subject="bridge", attribute="passable", value=False),
    )
    state1 = store.get_belief_state("guard-1")
    state2 = store.get_belief_state("guard-2")
    store.close()
    assert len(state1.predicates) == 1
    assert state1.predicates[0].subject == "king"
    assert len(state2.predicates) == 1
    assert state2.predicates[0].subject == "bridge"


def test_memory_store_works() -> None:
    """:memory: path should work as an in-process ephemeral store."""
    store = WorldOracleStore(":memory:")
    pred = WorldPredicate(subject="x", attribute="y", value=1)
    store.save_predicate("npc-1", pred)
    state = store.get_belief_state("npc-1")
    store.close()
    assert len(state.predicates) == 1


def test_get_repairs_filtered_by_predicate_id(tmp_db: str) -> None:
    """get_repairs(predicate_a_id=...) should filter correctly."""
    store = WorldOracleStore(tmp_db)
    r1 = RepairFrame(
        predicate_a_id="aaa", predicate_b_id="bbb",
        strategy="prefer_newer", resolved_value=True, reason="r1", timestamp=0.0,
    )
    r2 = RepairFrame(
        predicate_a_id="ccc", predicate_b_id="ddd",
        strategy="prefer_newer", resolved_value=False, reason="r2", timestamp=0.0,
    )
    store.save_repair(r1)
    store.save_repair(r2)
    repairs = store.get_repairs(predicate_a_id="aaa")
    store.close()
    assert len(repairs) == 1
    assert repairs[0].reason == "r1"


def test_get_belief_state_empty_npc(tmp_db: str) -> None:
    """get_belief_state for unknown NPC should return empty state."""
    store = WorldOracleStore(tmp_db)
    state = store.get_belief_state("nonexistent")
    store.close()
    assert state.predicates == []
    assert state.npc_id == "nonexistent"


def test_upsert_overwrites_predicate(tmp_db: str) -> None:
    """Saving the same predicate ID twice should not duplicate it."""
    store = WorldOracleStore(tmp_db)
    pred = WorldPredicate(subject="king", attribute="alive", value=True)
    store.save_predicate("guard-1", pred)
    store.save_predicate("guard-1", pred)
    state = store.get_belief_state("guard-1")
    store.close()
    assert len(state.predicates) == 1
