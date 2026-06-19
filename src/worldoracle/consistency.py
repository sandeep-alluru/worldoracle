"""Full consistency check with optional auto-repair."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from worldoracle.predicate import BeliefRepairer, ContradictionDetector
from worldoracle.store import WorldOracleStore


@dataclass
class ConsistencyReport:
    total_predicates: int
    contradictions_found: int
    contradictions_repaired: int
    unresolved: int
    consistency_score: float   # 0-1, 1 = fully consistent
    by_subject: dict[str, int]   # subject -> contradiction count
    most_contested: list[str]    # subjects with most contradictions (top 5)
    repair_summary: list[str]    # human-readable list of what was repaired


def full_consistency_check(store: WorldOracleStore, auto_repair: bool = True) -> ConsistencyReport:
    """Run a full consistency check across ALL NPCs and optionally auto-repair contradictions."""
    npc_ids = store.list_npc_ids()
    detector = ContradictionDetector()
    repairer = BeliefRepairer()

    total_predicates = 0
    all_contradictions: list[tuple] = []
    by_subject: dict[str, int] = defaultdict(int)

    for npc_id in npc_ids:
        state = store.get_belief_state(npc_id)
        total_predicates += len(state.predicates)
        pairs = detector.detect(state)
        for pred_a, pred_b in pairs:
            all_contradictions.append((pred_a, pred_b))
            by_subject[pred_a.subject] += 1

    contradictions_found = len(all_contradictions)
    contradictions_repaired = 0
    repair_summary: list[str] = []

    if auto_repair:
        for pred_a, pred_b in all_contradictions:
            frame = repairer.repair(pred_a, pred_b)
            store.save_repair(frame)
            # Remove the "losing" predicate
            loser = pred_a if pred_a.value != frame.resolved_value else pred_b
            store._conn.execute("DELETE FROM predicates WHERE id=?", (loser.id,))
            store._conn.commit()
            contradictions_repaired += 1
            repair_summary.append(
                f"Repaired: {pred_a.subject}.{pred_a.attribute} — "
                f"kept '{frame.resolved_value}' (strategy: {frame.strategy})"
            )

    unresolved = contradictions_found - contradictions_repaired

    if total_predicates == 0:
        consistency_score = 1.0
    else:
        consistency_score = 1.0 - (contradictions_found / total_predicates)
    consistency_score = max(0.0, min(1.0, consistency_score))

    # most_contested: top 5 subjects by contradiction count
    most_contested = sorted(by_subject.keys(), key=lambda s: by_subject[s], reverse=True)[:5]

    return ConsistencyReport(
        total_predicates=total_predicates,
        contradictions_found=contradictions_found,
        contradictions_repaired=contradictions_repaired,
        unresolved=unresolved,
        consistency_score=consistency_score,
        by_subject=dict(by_subject),
        most_contested=most_contested,
        repair_summary=repair_summary,
    )
