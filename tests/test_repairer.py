"""Tests for BeliefRepairer and RepairFrame."""

from __future__ import annotations

import pytest

from worldoracle.predicate import BeliefRepairer, RepairFrame, WorldPredicate


@pytest.fixture
def repairer() -> BeliefRepairer:
    """Return a fresh BeliefRepairer."""
    return BeliefRepairer()


def test_prefer_newer_picks_higher_timestamp(repairer: BeliefRepairer) -> None:
    """prefer_newer should select the predicate with the higher timestamp."""
    older = WorldPredicate(subject="king", attribute="alive", value=True, timestamp=10.0)
    newer = WorldPredicate(subject="king", attribute="alive", value=False, timestamp=20.0)
    frame = repairer.repair(older, newer)
    assert frame.strategy == "prefer_newer"
    assert frame.resolved_value == False  # noqa: E712


def test_prefer_newer_picks_first_if_newer_is_first(repairer: BeliefRepairer) -> None:
    """prefer_newer should work regardless of argument order."""
    newer = WorldPredicate(subject="king", attribute="alive", value=False, timestamp=20.0)
    older = WorldPredicate(subject="king", attribute="alive", value=True, timestamp=10.0)
    frame = repairer.repair(newer, older)
    assert frame.strategy == "prefer_newer"
    assert frame.resolved_value == False  # noqa: E712


def test_prefer_higher_confidence(repairer: BeliefRepairer) -> None:
    """prefer_higher_confidence should select the higher-confidence predicate."""
    low = WorldPredicate(
        subject="king", attribute="alive", value=True, confidence=0.5, timestamp=0.0
    )
    high = WorldPredicate(
        subject="king", attribute="alive", value=False, confidence=0.9, timestamp=0.0
    )
    frame = repairer.repair(low, high)
    assert frame.strategy == "prefer_higher_confidence"
    assert frame.resolved_value == False  # noqa: E712


def test_prefer_observation(repairer: BeliefRepairer) -> None:
    """prefer_observation should select the predicate with source='observation'."""
    hearsay = WorldPredicate(
        subject="king", attribute="alive", value=True,
        source="rumor", confidence=1.0, timestamp=0.0,
    )
    observed = WorldPredicate(
        subject="king", attribute="alive", value=False,
        source="observation", confidence=1.0, timestamp=0.0,
    )
    frame = repairer.repair(hearsay, observed)
    assert frame.strategy == "prefer_observation"
    assert frame.resolved_value == False  # noqa: E712


def test_default_strategy_keeps_pred_a(repairer: BeliefRepairer) -> None:
    """When no strategy differentiates, default to pred_a's value."""
    a = WorldPredicate(
        subject="king", attribute="alive", value=True,
        source="rumor", confidence=1.0, timestamp=0.0,
    )
    b = WorldPredicate(
        subject="king", attribute="alive", value=False,
        source="rumor", confidence=1.0, timestamp=0.0,
    )
    frame = repairer.repair(a, b)
    assert frame.resolved_value == True  # noqa: E712


def test_repair_frame_has_correct_strategy_field(repairer: BeliefRepairer) -> None:
    """Returned RepairFrame must have a non-empty strategy field."""
    a = WorldPredicate(subject="king", attribute="alive", value=True)
    b = WorldPredicate(subject="king", attribute="alive", value=False)
    frame = repairer.repair(a, b)
    assert isinstance(frame, RepairFrame)
    assert frame.strategy in {"prefer_newer", "prefer_higher_confidence", "prefer_observation"}


def test_repair_frame_id_is_content_addressed(repairer: BeliefRepairer) -> None:
    """Two RepairFrames for the same predicates and strategy should share the same ID."""
    a = WorldPredicate(subject="king", attribute="alive", value=True, timestamp=0.0, confidence=1.0)
    b = WorldPredicate(
        subject="king", attribute="alive", value=False, timestamp=0.0, confidence=1.0
    )
    frame1 = repairer.repair(a, b)
    frame2 = repairer.repair(a, b)
    assert frame1.id == frame2.id


def test_repair_frame_to_dict_keys() -> None:
    """RepairFrame.to_dict() should return all expected keys."""
    frame = RepairFrame(
        predicate_a_id="abc",
        predicate_b_id="def",
        strategy="prefer_newer",
        resolved_value=True,
        reason="test",
        timestamp=0.0,
    )
    d = frame.to_dict()
    expected = {
        "id", "predicate_a_id", "predicate_b_id",
        "strategy", "resolved_value", "reason", "timestamp",
    }
    assert set(d.keys()) == expected
