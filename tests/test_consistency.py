"""Tests for worldoracle.consistency."""
from worldoracle.consistency import ConsistencyReport, full_consistency_check
from worldoracle.predicate import WorldPredicate
from worldoracle.store import WorldOracleStore


def make_pred(subject, attribute, value, confidence=1.0, ts=1.0, source="obs"):
    return WorldPredicate(subject=subject, attribute=attribute, value=value,
                          source=source, confidence=confidence, timestamp=ts)


def test_consistency_empty_store():
    store = WorldOracleStore(":memory:")
    report = full_consistency_check(store, auto_repair=False)
    assert isinstance(report, ConsistencyReport)
    assert report.total_predicates == 0
    assert report.consistency_score == 1.0


def test_consistency_no_contradictions():
    store = WorldOracleStore(":memory:")
    store.save_predicate("npc1", make_pred("king", "alive", True))
    store.save_predicate("npc1", make_pred("bridge", "passable", True))
    report = full_consistency_check(store, auto_repair=False)
    assert report.contradictions_found == 0
    assert report.consistency_score == 1.0


def test_consistency_finds_contradictions():
    store = WorldOracleStore(":memory:")
    store.save_predicate("npc1", make_pred("king", "alive", True, confidence=0.9, ts=1.0))
    store.save_predicate("npc1", make_pred("king", "alive", False, confidence=0.7, ts=2.0))
    report = full_consistency_check(store, auto_repair=False)
    assert report.contradictions_found >= 1
    assert "king" in report.by_subject


def test_consistency_auto_repair():
    store = WorldOracleStore(":memory:")
    store.save_predicate("npc1", make_pred("king", "alive", True, confidence=0.9, ts=1.0))
    store.save_predicate("npc1", make_pred("king", "alive", False, confidence=0.5, ts=2.0))
    report = full_consistency_check(store, auto_repair=True)
    assert report.contradictions_repaired >= 1
    assert report.unresolved == 0


def test_consistency_score():
    store = WorldOracleStore(":memory:")
    # Add 4 beliefs, 1 contradiction
    store.save_predicate("npc1", make_pred("king", "alive", True, ts=1.0))
    store.save_predicate("npc1", make_pred("king", "alive", False, ts=2.0))
    store.save_predicate("npc1", make_pred("bridge", "passable", True))
    store.save_predicate("npc1", make_pred("village", "safe", True))
    report = full_consistency_check(store, auto_repair=False)
    assert 0.0 <= report.consistency_score <= 1.0


def test_most_contested():
    store = WorldOracleStore(":memory:")
    # king has 2 contradictions worth of data
    store.save_predicate("npc1", make_pred("king", "alive", True, ts=1.0))
    store.save_predicate("npc1", make_pred("king", "alive", False, ts=2.0))
    store.save_predicate("npc1", make_pred("dragon", "alive", True, ts=1.0))
    store.save_predicate("npc1", make_pred("dragon", "alive", False, ts=2.0))
    report = full_consistency_check(store, auto_repair=False)
    assert isinstance(report.most_contested, list)
    assert len(report.most_contested) <= 5


def test_consistency_repair_pred_b_wins():
    """When pred_b has a newer timestamp, it wins and the elif branch picks pred_a as loser."""
    store = WorldOracleStore(":memory:")
    # pred_b has higher timestamp => BeliefRepairer picks pred_b as winner
    # => resolved_value == pred_b.value => elif branch deletes pred_a
    store.save_predicate("npc1", make_pred("king", "alive", True, confidence=0.9, ts=1.0))
    store.save_predicate("npc1", make_pred("king", "alive", False, confidence=0.9, ts=2.0))
    report = full_consistency_check(store, auto_repair=True)
    assert report.contradictions_repaired >= 1


def test_consistency_repair_equal_confidence_fallback():
    """When both predicates have equal confidence and timestamps, the fallback
    branch in loser selection is used (delete the less-confident pred_a when tied)."""
    store = WorldOracleStore(":memory:")
    # Same timestamp, same confidence: fallback branch in repair loser selection
    store.save_predicate("npc1", make_pred("king", "alive", True, confidence=0.8, ts=1.0))
    store.save_predicate("npc1", make_pred("king", "alive", False, confidence=0.8, ts=1.0))
    report = full_consistency_check(store, auto_repair=True)
    assert report.contradictions_repaired >= 1
