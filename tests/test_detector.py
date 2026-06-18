"""Tests for ContradictionDetector."""

from __future__ import annotations

import pytest

from worldoracle.predicate import BeliefState, ContradictionDetector, WorldPredicate


@pytest.fixture
def detector() -> ContradictionDetector:
    """Return a fresh ContradictionDetector."""
    return ContradictionDetector()


def _make_state(npc_id: str = "guard") -> BeliefState:
    return BeliefState(npc_id=npc_id)


def test_detect_bool_contradiction(detector: ContradictionDetector) -> None:
    """True vs False on same subject+attribute is a contradiction."""
    state = _make_state()
    state.add(WorldPredicate(subject="king", attribute="alive", value=True))
    state.add(WorldPredicate(subject="king", attribute="alive", value=False))
    pairs = detector.detect(state)
    assert len(pairs) == 1


def test_no_false_positives_for_consistent_beliefs(detector: ContradictionDetector) -> None:
    """Consistent beliefs produce no contradictions."""
    state = _make_state()
    state.add(WorldPredicate(subject="king", attribute="alive", value=True))
    state.add(WorldPredicate(subject="queen", attribute="alive", value=False))
    assert detector.detect(state) == []


def test_multiple_contradictions_detected(detector: ContradictionDetector) -> None:
    """Multiple contradicting pairs across different keys are all detected."""
    state = _make_state()
    state.add(WorldPredicate(subject="king", attribute="alive", value=True))
    state.add(WorldPredicate(subject="king", attribute="alive", value=False))
    state.add(WorldPredicate(subject="bridge", attribute="passable", value=True))
    state.add(WorldPredicate(subject="bridge", attribute="passable", value=False))
    pairs = detector.detect(state)
    assert len(pairs) == 2


def test_different_subject_no_contradiction(detector: ContradictionDetector) -> None:
    """Same attribute, different subjects — not a contradiction."""
    state = _make_state()
    state.add(WorldPredicate(subject="king", attribute="alive", value=True))
    state.add(WorldPredicate(subject="queen", attribute="alive", value=False))
    assert detector.detect(state) == []


def test_different_attribute_no_contradiction(detector: ContradictionDetector) -> None:
    """Same subject, different attributes — not a contradiction."""
    state = _make_state()
    state.add(WorldPredicate(subject="king", attribute="alive", value=True))
    state.add(WorldPredicate(subject="king", attribute="crowned", value=False))
    assert detector.detect(state) == []


def test_same_value_no_contradiction(detector: ContradictionDetector) -> None:
    """Same subject+attribute+value — not a contradiction."""
    state = _make_state()
    state.add(WorldPredicate(subject="king", attribute="alive", value=True))
    state.add(WorldPredicate(subject="king", attribute="alive", value=True))
    assert detector.detect(state) == []


def test_empty_state_no_contradiction(detector: ContradictionDetector) -> None:
    """Empty state produces no contradictions."""
    state = _make_state()
    assert detector.detect(state) == []


def test_single_predicate_no_contradiction(detector: ContradictionDetector) -> None:
    """A state with only one predicate has no contradictions."""
    state = _make_state()
    state.add(WorldPredicate(subject="king", attribute="alive", value=True))
    assert detector.detect(state) == []


def test_contradiction_pair_has_correct_subjects(detector: ContradictionDetector) -> None:
    """The returned pair should reference the original predicates."""
    state = _make_state()
    p1 = WorldPredicate(subject="king", attribute="alive", value=True)
    p2 = WorldPredicate(subject="king", attribute="alive", value=False)
    state.add(p1)
    state.add(p2)
    pairs = detector.detect(state)
    a, b = pairs[0]
    ids = {a.id, b.id}
    assert p1.id in ids
    assert p2.id in ids
