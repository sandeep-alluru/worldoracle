"""worldoracle — NPC contradiction detector and belief repair for game worlds."""

from __future__ import annotations

from importlib.metadata import version as _version

from worldoracle.predicate import (
    BeliefRepairer,
    BeliefState,
    ContradictionDetector,
    RepairFrame,
    WorldPredicate,
)
from worldoracle.report import print_beliefs, print_repairs, to_json, to_markdown
from worldoracle.store import WorldOracleStore

__version__ = _version("worldoracle")

__all__ = [
    "BeliefRepairer",
    "BeliefState",
    "ContradictionDetector",
    "RepairFrame",
    "WorldOracleStore",
    "WorldPredicate",
    "print_beliefs",
    "print_repairs",
    "to_json",
    "to_markdown",
]
