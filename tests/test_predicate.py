"""Tests for worldoracle.predicate — WorldPredicate, BeliefState."""

from __future__ import annotations

import hashlib

from worldoracle.predicate import BeliefState, WorldPredicate

# ── WorldPredicate ─────────────────────────────────────────────────────────────


def test_predicate_id_is_sha256_of_content() -> None:
    """ID should be SHA-256[:16] of 'subject|attribute|str(value)'."""
    pred = WorldPredicate(subject="king", attribute="alive", value=True)
    payload = "king|alive|True"
    expected = hashlib.sha256(payload.encode()).hexdigest()[:16]
    assert pred.id == expected


def test_predicate_same_content_same_id() -> None:
    """Two predicates with identical content should share the same ID."""
    a = WorldPredicate(subject="king", attribute="alive", value=True)
    b = WorldPredicate(subject="king", attribute="alive", value=True)
    assert a.id == b.id


def test_predicate_different_value_different_id() -> None:
    """Predicates with different values must have different IDs."""
    a = WorldPredicate(subject="king", attribute="alive", value=True)
    b = WorldPredicate(subject="king", attribute="alive", value=False)
    assert a.id != b.id


def test_predicate_to_dict_has_correct_keys() -> None:
    """to_dict() should return all expected keys."""
    pred = WorldPredicate(
        subject="bridge",
        attribute="passable",
        value="yes",
        source="scout",
        confidence=0.8,
        timestamp=42.0,
    )
    d = pred.to_dict()
    expected_keys = {"id", "subject", "attribute", "value", "source", "confidence", "timestamp"}
    assert set(d.keys()) == expected_keys
    assert d["subject"] == "bridge"
    assert d["attribute"] == "passable"
    assert d["value"] == "yes"
    assert d["source"] == "scout"
    assert d["confidence"] == 0.8
    assert d["timestamp"] == 42.0


def test_predicate_from_dict_round_trip() -> None:
    """from_dict(to_dict()) should reproduce the same predicate."""
    original = WorldPredicate(
        subject="king",
        attribute="alive",
        value=True,
        source="observation",
        confidence=0.9,
        timestamp=100.0,
    )
    restored = WorldPredicate.from_dict(original.to_dict())
    assert restored.subject == original.subject
    assert restored.attribute == original.attribute
    assert restored.value == original.value
    assert restored.source == original.source
    assert restored.confidence == original.confidence
    assert restored.timestamp == original.timestamp
    assert restored.id == original.id


def test_predicate_from_dict_defaults() -> None:
    """from_dict() should use sensible defaults for optional keys."""
    pred = WorldPredicate.from_dict({"subject": "x", "attribute": "y", "value": 1})
    assert pred.source == ""
    assert pred.confidence == 1.0
    assert pred.timestamp == 0.0


def test_predicate_id_not_in_init() -> None:
    """id should be computed, not accepted as constructor argument."""
    pred = WorldPredicate(subject="a", attribute="b", value="c")
    assert pred.id  # non-empty string


def test_predicate_different_subject_different_id() -> None:
    """Predicates with different subjects must differ."""
    a = WorldPredicate(subject="king", attribute="alive", value=True)
    b = WorldPredicate(subject="queen", attribute="alive", value=True)
    assert a.id != b.id


# ── BeliefState ────────────────────────────────────────────────────────────────


def test_belief_state_starts_empty() -> None:
    """A new BeliefState should have an empty predicate list."""
    state = BeliefState(npc_id="guard-1")
    assert state.predicates == []
    assert state.id  # ID is still computed


def test_belief_state_id_recomputed_after_add() -> None:
    """BeliefState.id should change after adding a predicate."""
    state = BeliefState(npc_id="guard-1")
    id_before = state.id
    pred = WorldPredicate(subject="king", attribute="alive", value=True)
    state.add(pred)
    assert state.id != id_before


def test_belief_state_add_appends_predicate() -> None:
    """add() should append the predicate to state.predicates."""
    state = BeliefState(npc_id="guard-1")
    pred = WorldPredicate(subject="king", attribute="alive", value=True)
    state.add(pred)
    assert len(state.predicates) == 1
    assert state.predicates[0] is pred


def test_belief_state_get_filters_by_subject_and_attribute() -> None:
    """get() should return only predicates matching subject and attribute."""
    state = BeliefState(npc_id="guard-1")
    p1 = WorldPredicate(subject="king", attribute="alive", value=True)
    p2 = WorldPredicate(subject="king", attribute="alive", value=False)
    p3 = WorldPredicate(subject="queen", attribute="alive", value=True)
    state.add(p1)
    state.add(p2)
    state.add(p3)
    result = state.get("king", "alive")
    assert len(result) == 2
    assert p1 in result
    assert p2 in result


def test_belief_state_get_returns_empty_for_unknown() -> None:
    """get() should return [] when no matching predicates exist."""
    state = BeliefState(npc_id="guard-1")
    assert state.get("ghost", "attribute") == []


def test_belief_state_to_dict_structure() -> None:
    """to_dict() should have the correct structure."""
    state = BeliefState(npc_id="guard-1")
    pred = WorldPredicate(subject="king", attribute="alive", value=True)
    state.add(pred)
    d = state.to_dict()
    assert d["npc_id"] == "guard-1"
    assert "id" in d
    assert isinstance(d["predicates"], list)
    assert len(d["predicates"]) == 1
