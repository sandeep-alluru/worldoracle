"""Tests for worldoracle.diff."""
import time
import pytest
from worldoracle.store import WorldOracleStore
from worldoracle.predicate import WorldPredicate
from worldoracle.temporal import TemporalBeliefStore
from worldoracle.diff import BeliefChange, BeliefDiff, diff_belief_states


def make_pred(subject="king", attribute="alive", value=True, confidence=0.9, ts=1.0):
    return WorldPredicate(subject=subject, attribute=attribute, value=value,
                          source="obs", confidence=confidence, timestamp=ts)


def test_diff_no_snapshot_data():
    store = WorldOracleStore(":memory:")
    result = diff_belief_states(store, 0.0, time.time())
    assert isinstance(result, BeliefDiff)
    assert result.before_count == 0
    assert result.after_count == 0


def test_diff_added():
    store = WorldOracleStore(":memory:")
    ts = TemporalBeliefStore(store)
    before_ts = time.time()
    ts.record_snapshot()  # empty snapshot
    pred = make_pred()
    store.save_predicate("npc1", pred)
    after_ts = time.time()
    ts.record_snapshot()
    result = diff_belief_states(store, before_ts, after_ts + 1)
    assert result.added >= 1
    assert any(c.change_type == "added" for c in result.changes)


def test_diff_summary_string():
    store = WorldOracleStore(":memory:")
    ts = TemporalBeliefStore(store)
    ts.record_snapshot()
    before_ts = time.time()
    after_ts = time.time() + 1
    ts.record_snapshot()
    result = diff_belief_states(store, before_ts, after_ts + 1)
    assert isinstance(result.summary, str)
    assert "Before:" in result.summary


def test_diff_stable_beliefs():
    store = WorldOracleStore(":memory:")
    pred = make_pred()
    store.save_predicate("npc1", pred)
    ts = TemporalBeliefStore(store)
    ts.record_snapshot()
    before_ts = time.time()
    ts.record_snapshot()
    after_ts = time.time() + 1
    result = diff_belief_states(store, before_ts, after_ts)
    assert result.stable >= 1


def test_diff_with_subject_filter():
    store = WorldOracleStore(":memory:")
    pred = make_pred(subject="king")
    store.save_predicate("npc1", pred)
    ts = TemporalBeliefStore(store)
    before_ts = time.time() - 1
    ts.record_snapshot()
    after_ts = time.time() + 1
    ts.record_snapshot()
    result = diff_belief_states(store, before_ts, after_ts + 1, subject="king")
    assert isinstance(result, BeliefDiff)


def test_diff_removed():
    """Belief present before but absent after -> removed."""
    store = WorldOracleStore(":memory:")
    ts = TemporalBeliefStore(store)
    # Manually insert snapshot rows at controlled timestamps
    conn = store._conn
    conn.execute(
        "INSERT INTO snapshot_registry (taken_at) VALUES (?)", (1000.0,)
    )
    conn.execute(
        """INSERT INTO belief_snapshots
           (snapshot_id, snapshot_ts, npc_id, subject, attribute, value, confidence, source)
           VALUES (1, 1000.0, 'npc1', 'king', 'alive', 'true', 0.9, 'obs')"""
    )
    conn.execute(
        "INSERT INTO snapshot_registry (taken_at) VALUES (?)", (2000.0,)
    )
    # No rows for snapshot 2 — belief was removed
    conn.commit()
    result = diff_belief_states(store, 1500.0, 2500.0)
    assert result.removed >= 1
    assert any(c.change_type == "removed" for c in result.changes)


def test_diff_value_changed():
    """Belief value changes between snapshots -> value_changed."""
    store = WorldOracleStore(":memory:")
    ts = TemporalBeliefStore(store)
    conn = store._conn
    conn.execute(
        "INSERT INTO snapshot_registry (taken_at) VALUES (?)", (1000.0,)
    )
    conn.execute(
        """INSERT INTO belief_snapshots
           (snapshot_id, snapshot_ts, npc_id, subject, attribute, value, confidence, source)
           VALUES (1, 1000.0, 'npc1', 'king', 'alive', '"old"', 0.9, 'obs')"""
    )
    conn.execute(
        "INSERT INTO snapshot_registry (taken_at) VALUES (?)", (2000.0,)
    )
    conn.execute(
        """INSERT INTO belief_snapshots
           (snapshot_id, snapshot_ts, npc_id, subject, attribute, value, confidence, source)
           VALUES (2, 2000.0, 'npc1', 'king', 'alive', '"new"', 0.9, 'obs')"""
    )
    conn.commit()
    result = diff_belief_states(store, 1500.0, 2500.0)
    assert result.modified >= 1
    assert any(c.change_type == "value_changed" for c in result.changes)


def test_diff_confidence_changed():
    """Same value, different confidence -> confidence_changed."""
    store = WorldOracleStore(":memory:")
    ts = TemporalBeliefStore(store)
    conn = store._conn
    conn.execute(
        "INSERT INTO snapshot_registry (taken_at) VALUES (?)", (1000.0,)
    )
    conn.execute(
        """INSERT INTO belief_snapshots
           (snapshot_id, snapshot_ts, npc_id, subject, attribute, value, confidence, source)
           VALUES (1, 1000.0, 'npc1', 'king', 'alive', '"alive"', 0.5, 'obs')"""
    )
    conn.execute(
        "INSERT INTO snapshot_registry (taken_at) VALUES (?)", (2000.0,)
    )
    conn.execute(
        """INSERT INTO belief_snapshots
           (snapshot_id, snapshot_ts, npc_id, subject, attribute, value, confidence, source)
           VALUES (2, 2000.0, 'npc1', 'king', 'alive', '"alive"', 0.9, 'obs')"""
    )
    conn.commit()
    result = diff_belief_states(store, 1500.0, 2500.0)
    assert result.modified >= 1
    assert any(c.change_type == "confidence_changed" for c in result.changes)
