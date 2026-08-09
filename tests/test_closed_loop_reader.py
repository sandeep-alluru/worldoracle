"""Closed-loop gate - empty store and legal human_required (farm cases)."""

import pytest

from worldoracle.closed_loop import ClosedLoopError, assert_beliefs_clean, gate_beliefs
from worldoracle.predicate import WorldPredicate
from worldoracle.store import WorldOracleStore


def pred(subject, attribute, value, confidence=1.0, ts=1.0):
    return WorldPredicate(
        subject=subject,
        attribute=attribute,
        value=value,
        source="test",
        confidence=confidence,
        timestamp=ts,
    )


def test_empty_store_fails_loud_phase_guard():
    """G-CONTRA-ORDER: refuse consistency check before data exists."""
    store = WorldOracleStore(":memory:")
    out = gate_beliefs(store, mode="human_required")
    assert out.ok is False
    assert out.verdict == "FAIL_LOUD"
    assert out.exit_code == 2
    assert "empty" in out.reason.lower() or "before data" in out.reason.lower()


def test_min_predicates_phase_guard():
    """Too few predicates = phase too early for contradiction gate."""
    store = WorldOracleStore(":memory:")
    store.save_predicate("npc1", pred("king", "alive", True))
    out = gate_beliefs(store, mode="human_required", min_predicates=5)
    assert out.ok is False
    assert out.verdict == "FAIL_LOUD"
    assert "predicate" in out.reason.lower() or "phase" in out.reason.lower()


def test_clean_beliefs_pass():
    store = WorldOracleStore(":memory:")
    store.save_predicate("npc1", pred("king", "alive", True))
    out = gate_beliefs(store, mode="human_required")
    assert out.ok is True
    assert out.verdict == "PASS"
    assert out.exit_code == 0


def test_contradiction_human_required_no_silent_pass():
    """LEGAL-NO-AUTOFIX: contradictions demand human, not auto ok."""
    store = WorldOracleStore(":memory:")
    store.save_predicate("npc1", pred("king", "alive", True, ts=1.0))
    store.save_predicate("npc1", pred("king", "alive", False, ts=2.0))
    out = gate_beliefs(store, mode="human_required")
    assert out.ok is False
    assert out.human_required is True
    assert out.exit_code == 1
    assert out.contradictions_found >= 1


def test_auto_repair_mode_explicit_only():
    """auto_repair must be opt-in; default remains human_required."""
    store = WorldOracleStore(":memory:")
    store.save_predicate("npc1", pred("king", "alive", True, ts=1.0))
    store.save_predicate("npc1", pred("king", "alive", False, ts=2.0))
    human = gate_beliefs(store, mode="human_required")
    assert human.human_required is True
    # report mode also fails without claiming repair
    rep = gate_beliefs(store, mode="report")
    assert rep.ok is False
    assert rep.human_required is False


def test_assert_beliefs_clean_raises():
    store = WorldOracleStore(":memory:")
    with pytest.raises(ClosedLoopError, match="FAIL_LOUD"):
        assert_beliefs_clean(store)
