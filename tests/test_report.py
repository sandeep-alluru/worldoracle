"""Tests for worldoracle.report — print_beliefs, print_repairs, to_json, to_markdown."""

from __future__ import annotations

import json

import pytest
from rich.console import Console

from worldoracle.predicate import BeliefState, RepairFrame, WorldPredicate
from worldoracle.report import print_beliefs, print_repairs, to_json, to_markdown


@pytest.fixture
def state_with_predicates() -> BeliefState:
    """BeliefState with two predicates."""
    state = BeliefState(npc_id="guard-1")
    state.add(WorldPredicate(subject="king", attribute="alive", value=True, source="observation"))
    state.add(WorldPredicate(subject="bridge", attribute="passable", value=False, source="rumor"))
    return state


def test_print_beliefs_does_not_crash(state_with_predicates: BeliefState) -> None:
    """print_beliefs should not raise."""
    console = Console(file=open("/dev/null", "w"))
    print_beliefs(state_with_predicates, console=console)


def test_print_repairs_empty_list_no_crash() -> None:
    """print_repairs with empty list should print 'No repairs needed'."""
    console = Console(file=open("/dev/null", "w"))
    print_repairs([], console=console)


def test_print_repairs_with_repairs(state_with_predicates: BeliefState) -> None:
    """print_repairs with a list of repairs should not raise."""
    repair = RepairFrame(
        predicate_a_id="aaa",
        predicate_b_id="bbb",
        strategy="prefer_newer",
        resolved_value=True,
        reason="test",
        timestamp=0.0,
    )
    console = Console(file=open("/dev/null", "w"))
    print_repairs([repair], console=console)


def test_to_json_returns_valid_json(state_with_predicates: BeliefState) -> None:
    """to_json() should return a valid JSON string."""
    result = to_json(state_with_predicates)
    data = json.loads(result)
    assert data["npc_id"] == "guard-1"
    assert isinstance(data["predicates"], list)
    assert len(data["predicates"]) == 2


def test_to_json_includes_repairs_when_provided(state_with_predicates: BeliefState) -> None:
    """to_json(repairs=[...]) should include repairs key."""
    repair = RepairFrame(
        predicate_a_id="aaa",
        predicate_b_id="bbb",
        strategy="prefer_newer",
        resolved_value=True,
        reason="test",
        timestamp=0.0,
    )
    result = to_json(state_with_predicates, repairs=[repair])
    data = json.loads(result)
    assert "repairs" in data
    assert len(data["repairs"]) == 1


def test_to_json_no_repairs_key_when_none(state_with_predicates: BeliefState) -> None:
    """to_json() without repairs should not include the repairs key."""
    result = to_json(state_with_predicates)
    data = json.loads(result)
    assert "repairs" not in data


def test_to_markdown_has_table_headers() -> None:
    """to_markdown() should contain markdown table header characters."""
    state = BeliefState(npc_id="guard-1")
    state.add(WorldPredicate(subject="king", attribute="alive", value=True))
    result = to_markdown([state])
    assert "| Subject |" in result
    assert "| Attribute |" in result


def test_to_markdown_has_npc_heading() -> None:
    """to_markdown() should include the NPC id as a heading."""
    state = BeliefState(npc_id="guard-1")
    result = to_markdown([state])
    assert "guard-1" in result


def test_to_markdown_empty_states() -> None:
    """to_markdown([]) should return a non-empty header string."""
    result = to_markdown([])
    assert "worldoracle" in result
