"""Tests for worldoracle.temporal."""
import time
import pytest
from worldoracle.store import WorldOracleStore
from worldoracle.predicate import WorldPredicate
from worldoracle.temporal import BeliefSnapshot, TemporalBeliefStore


def make_pred(subject="king", attribute="alive", value=True, confidence=0.9, ts=1.0):
    return WorldPredicate(subject=subject, attribute=attribute, value=value,
                          source="obs", confidence=confidence, timestamp=ts)


def test_record_snapshot_returns_id():
    store = WorldOracleStore(":memory:")
    pred = make_pred()
    store.save_predicate("npc1", pred)
    ts = TemporalBeliefStore(store)
    snap_id = ts.record_snapshot()
    assert isinstance(snap_id, int)
    assert snap_id >= 1


def test_get_belief_at_returns_snapshot():
    store = WorldOracleStore(":memory:")
    pred = make_pred()
    store.save_predicate("npc1", pred)
    ts = TemporalBeliefStore(store)
    ts.record_snapshot()
    snap = ts.get_belief_at("king", "alive", time.time() + 10)
    assert snap is not None
    assert snap.subject == "king"
    assert snap.predicate == "alive"


def test_get_belief_at_before_snapshot_returns_none():
    store = WorldOracleStore(":memory:")
    pred = make_pred()
    store.save_predicate("npc1", pred)
    ts = TemporalBeliefStore(store)
    before = time.time() - 100
    ts.record_snapshot()
    snap = ts.get_belief_at("king", "alive", before)
    assert snap is None


def test_get_belief_history():
    store = WorldOracleStore(":memory:")
    pred = make_pred(confidence=0.9)
    store.save_predicate("npc1", pred)
    ts = TemporalBeliefStore(store)
    ts.record_snapshot()
    ts.record_snapshot()
    history = ts.get_belief_history("king", "alive")
    assert len(history) >= 1
    assert all(isinstance(h, BeliefSnapshot) for h in history)


def test_belief_drift_stable():
    store = WorldOracleStore(":memory:")
    pred = make_pred(confidence=0.8)
    store.save_predicate("npc1", pred)
    ts = TemporalBeliefStore(store)
    ts.record_snapshot()
    ts.record_snapshot()  # Same data
    drift = ts.belief_drift("king", "alive")
    assert 0.0 <= drift <= 1.0
    assert drift == 0.0  # confidence unchanged


def test_belief_drift_volatile():
    store = WorldOracleStore(":memory:")
    pred1 = make_pred(confidence=0.2)
    store.save_predicate("npc1", pred1)
    ts = TemporalBeliefStore(store)
    ts.record_snapshot()
    # Update predicate with different confidence
    pred2 = WorldPredicate(subject="king", attribute="alive", value=True,
                           source="obs", confidence=0.9, timestamp=2.0)
    store.save_predicate("npc1", pred2)
    ts.record_snapshot()
    drift = ts.belief_drift("king", "alive")
    assert drift > 0.0


def test_belief_drift_no_history():
    """belief_drift returns 0.0 when fewer than 2 snapshots exist."""
    store = WorldOracleStore(":memory:")
    ts = TemporalBeliefStore(store)
    drift = ts.belief_drift("nonexistent", "alive")
    assert drift == 0.0


def test_get_belief_history_json_string_value():
    """get_belief_history correctly parses a JSON-encoded string value."""
    store = WorldOracleStore(":memory:")
    pred = make_pred(value="hello")
    store.save_predicate("npc1", pred)
    ts = TemporalBeliefStore(store)
    ts.record_snapshot()
    history = ts.get_belief_history("king", "alive")
    assert len(history) >= 1
    # Value should be correctly resolved (json string -> str)
    assert isinstance(history[0].value, str)
