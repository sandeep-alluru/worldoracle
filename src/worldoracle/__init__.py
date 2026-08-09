"""worldoracle - NPC contradiction detector and belief repair for game worlds."""

from __future__ import annotations

from importlib.metadata import version as _version

from worldoracle.closed_loop import (
    ClosedLoopError,
    GateOutcome,
    assert_beliefs_clean,
    gate_beliefs,
)
from worldoracle.collective import (
    AgentVote,
    ConsensusCertificate,
    assert_collective_consensus_ok,
    certify_consensus,
    estimate_deadline,
    gate_collective_consensus,
)
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
    "AgentVote",
    "BeliefChange",
    "BeliefDiff",
    "BeliefRepairer",
    "BeliefSnapshot",
    "BeliefState",
    "ClosedLoopError",
    "ConsensusCertificate",
    "ConsistencyReport",
    "ContradictionDetector",
    "GateOutcome",
    "RepairFrame",
    "TemporalBeliefStore",
    "WorldOracleStore",
    "WorldPredicate",
    "assert_beliefs_clean",
    "assert_collective_consensus_ok",
    "certify_consensus",
    "diff_belief_states",
    "estimate_deadline",
    "full_consistency_check",
    "gate_beliefs",
    "gate_collective_consensus",
    "print_beliefs",
    "print_repairs",
    "to_json",
    "to_markdown",
]
