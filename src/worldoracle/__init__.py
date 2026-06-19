"""worldoracle — NPC contradiction detector and belief repair for game worlds."""

from __future__ import annotations

from importlib.metadata import version as _version

from worldoracle.consistency import ConsistencyReport, full_consistency_check
from worldoracle.diff import BeliefChange, BeliefDiff, diff_belief_states
from worldoracle.predicate import (
    BeliefRepairer,
    BeliefState,
    ContradictionDetector,
    RepairFrame,
    WorldPredicate,
)
from worldoracle.report import print_beliefs, print_repairs, to_json, to_markdown
from worldoracle.store import WorldOracleStore
from worldoracle.temporal import BeliefSnapshot, TemporalBeliefStore

__version__ = _version("worldoracle")

__all__ = [
    "BeliefChange",
    "BeliefDiff",
    "BeliefRepairer",
    "BeliefSnapshot",
    "BeliefState",
    "ConsistencyReport",
    "ContradictionDetector",
    "RepairFrame",
    "TemporalBeliefStore",
    "WorldOracleStore",
    "WorldPredicate",
    "diff_belief_states",
    "full_consistency_check",
    "print_beliefs",
    "print_repairs",
    "to_json",
    "to_markdown",
]
