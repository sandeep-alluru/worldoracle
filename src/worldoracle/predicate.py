"""Core data model: WorldPredicate, BeliefState, ContradictionDetector, BeliefRepairer."""

from __future__ import annotations

import hashlib
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorldPredicate:
    """A belief predicate: subject has attribute=value."""

    subject: str  # "king", "player-1", "bridge-3"
    attribute: str  # "alive", "allied", "passable"
    value: Any  # True/False/str/float
    source: str = ""  # who told the NPC this: "quest-giver", "observation"
    confidence: float = 1.0
    timestamp: float = 0.0
    id: str = field(init=False)  # SHA-256[:16] of subject|attribute|str(value)

    def __post_init__(self) -> None:
        """Compute content-addressed ID."""
        payload = f"{self.subject}|{self.attribute}|{self.value!s}"
        self.id = hashlib.sha256(payload.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "id": self.id,
            "subject": self.subject,
            "attribute": self.attribute,
            "value": self.value,
            "source": self.source,
            "confidence": self.confidence,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> WorldPredicate:
        """Deserialize from dict."""
        return cls(
            subject=d["subject"],
            attribute=d["attribute"],
            value=d["value"],
            source=d.get("source", ""),
            confidence=d.get("confidence", 1.0),
            timestamp=d.get("timestamp", 0.0),
        )


@dataclass
class BeliefState:
    """An NPC's belief state: a set of WorldPredicates."""

    npc_id: str
    predicates: list[WorldPredicate] = field(default_factory=list)
    id: str = field(init=False)

    def __post_init__(self) -> None:
        """Compute initial content-addressed ID."""
        self._recompute_id()

    def _recompute_id(self) -> None:
        """Recompute the content-addressed ID from all predicate IDs."""
        pred_ids = sorted(p.id for p in self.predicates)
        payload = self.npc_id + "|" + "|".join(pred_ids)
        self.id = hashlib.sha256(payload.encode()).hexdigest()[:16]

    def add(self, pred: WorldPredicate) -> None:
        """Add a predicate and recompute ID. Skips duplicates by content ID."""
        if any(p.id == pred.id for p in self.predicates):
            return
        self.predicates.append(pred)
        self._recompute_id()

    def get(self, subject: str, attribute: str) -> list[WorldPredicate]:
        """Get predicates matching subject and attribute."""
        return [p for p in self.predicates if p.subject == subject and p.attribute == attribute]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "id": self.id,
            "npc_id": self.npc_id,
            "predicates": [p.to_dict() for p in self.predicates],
        }


@dataclass
class ContradictionDetector:
    """Find contradictions in a BeliefState."""

    def detect(self, state: BeliefState) -> list[tuple[WorldPredicate, WorldPredicate]]:
        """Return pairs of contradicting predicates (same subject+attribute, different values)."""
        pairs: list[tuple[WorldPredicate, WorldPredicate]] = []
        groups: dict[tuple[str, str], list[WorldPredicate]] = defaultdict(list)
        for p in state.predicates:
            groups[(p.subject, p.attribute)].append(p)
        for _key, preds in groups.items():
            if len(preds) < 2:
                continue
            for i in range(len(preds)):
                for j in range(i + 1, len(preds)):
                    a, b = preds[i], preds[j]
                    if a.value != b.value and a.value is not None and b.value is not None:
                        pairs.append((a, b))
        return pairs


@dataclass
class RepairFrame:
    """A suggested repair for a contradiction."""

    predicate_a_id: str
    predicate_b_id: str
    strategy: str  # "prefer_newer", "prefer_higher_confidence", "prefer_observation"
    resolved_value: Any
    reason: str
    timestamp: float = 0.0
    id: str = field(init=False)

    def __post_init__(self) -> None:
        """Compute content-addressed ID."""
        payload = f"{self.predicate_a_id}|{self.predicate_b_id}|{self.strategy}"
        self.id = hashlib.sha256(payload.encode()).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "id": self.id,
            "predicate_a_id": self.predicate_a_id,
            "predicate_b_id": self.predicate_b_id,
            "strategy": self.strategy,
            "resolved_value": self.resolved_value,
            "reason": self.reason,
            "timestamp": self.timestamp,
        }


class BeliefRepairer:
    """Generate RepairFrames for contradictions."""

    def repair(self, pred_a: WorldPredicate, pred_b: WorldPredicate) -> RepairFrame:
        """Apply repair strategies in priority order."""
        now = time.time()
        # 1. prefer_newer
        if pred_a.timestamp != pred_b.timestamp:
            winner = pred_a if pred_a.timestamp > pred_b.timestamp else pred_b
            return RepairFrame(
                predicate_a_id=pred_a.id,
                predicate_b_id=pred_b.id,
                strategy="prefer_newer",
                resolved_value=winner.value,
                reason=f"Keeping newer belief (timestamp {winner.timestamp})",
                timestamp=now,
            )
        # 2. prefer_higher_confidence
        if pred_a.confidence != pred_b.confidence:
            winner = pred_a if pred_a.confidence > pred_b.confidence else pred_b
            return RepairFrame(
                predicate_a_id=pred_a.id,
                predicate_b_id=pred_b.id,
                strategy="prefer_higher_confidence",
                resolved_value=winner.value,
                reason=f"Keeping higher confidence belief ({winner.confidence:.2f})",
                timestamp=now,
            )
        # 3. prefer_observation
        if pred_a.source == "observation" or pred_b.source == "observation":
            winner = pred_a if pred_a.source == "observation" else pred_b
            return RepairFrame(
                predicate_a_id=pred_a.id,
                predicate_b_id=pred_b.id,
                strategy="prefer_observation",
                resolved_value=winner.value,
                reason="Preferring direct observation over hearsay",
                timestamp=now,
            )
        # Default: keep pred_a
        return RepairFrame(
            predicate_a_id=pred_a.id,
            predicate_b_id=pred_b.id,
            strategy="prefer_newer",
            resolved_value=pred_a.value,
            reason="No distinguishing strategy; defaulting to first predicate",
            timestamp=now,
        )
