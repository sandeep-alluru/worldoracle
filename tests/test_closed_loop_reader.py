"""Closed-loop gate — empty store and legal human_required (farm cases)."""

from worldoracle.closed_loop import assert_beliefs_clean, gate_beliefs
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
    store = WorldOracleStore(":memory:")
    out = gate_beliefs(store, mode="human_required")
    assert out.ok is False
    assert out.verdict == "FAIL_LOUD"
    assert out.exit_code == 2
    assert "empty" in out.reason.lower() or "before data" in out.reason.lower()


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


def test_assert_beliefs_clean_raises():
    store = WorldOracleStore(":memory:")
    try:
        assert_beliefs_clean(store)
        raised = False
    except RuntimeError:
        raised = True
    assert raised
