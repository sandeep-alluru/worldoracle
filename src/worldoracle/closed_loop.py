"""Closed-loop gates for worldoracle - farm_memory LEGAL-NO-AUTOFIX / G-CONTRA.

Real-world cases (Qdrant):
- LEGAL GATES ALWAYS STOP FOR HUMAN - NEVER AUTO-FIX: G-CONTRA, G-FOOTAGE-THEME, ...
- check_contradictions ran BEFORE data existed (phase order) → false blocks
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from worldoracle.consistency import full_consistency_check
from worldoracle.store import WorldOracleStore

Mode = Literal["report", "auto_repair", "human_required"]


@dataclass(frozen=True)
class GateOutcome:
    ok: bool
    verdict: str
    reason: str
    exit_code: int
    consistency_score: float | None = None
    contradictions_found: int = 0
    human_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "verdict": self.verdict,
            "reason": self.reason,
            "exit_code": self.exit_code,
            "consistency_score": self.consistency_score,
            "contradictions_found": self.contradictions_found,
            "human_required": self.human_required,
        }


def _fail_loud(reason: str) -> GateOutcome:
    return GateOutcome(False, "FAIL_LOUD", reason, 2, None, 0, False)


def gate_beliefs(
    store: WorldOracleStore,
    *,
    mode: Mode = "human_required",
    min_predicates: int = 1,
) -> GateOutcome:
    """Run consistency check with explicit repair policy.

    Modes:
    - report: detect only, ok if score==1
    - auto_repair: allow automatic repair (NOT for legal gates)
    - human_required: if any contradiction, FAIL and demand human
      (default - matches farm rule LEGAL GATES NEVER AUTO-FIX)

    Phase guard: empty store → FAIL_LOUD (do not run contradiction
    checks before data exists - Foundry G-CONTRA ordering bug).
    """
    npc_ids = store.list_npc_ids()
    if not npc_ids:
        return _fail_loud(
            "empty belief store - refuse consistency check before data exists "
            "(Foundry: G-CONTRA ran before clips existed)"
        )

    total = 0
    for nid in npc_ids:
        total += len(store.get_belief_state(nid).predicates)
    if total < min_predicates:
        return _fail_loud(
            f"only {total} predicates (<{min_predicates}) - phase too early for contradiction gate"
        )

    if mode == "auto_repair":
        report = full_consistency_check(store, auto_repair=True)
    else:
        report = full_consistency_check(store, auto_repair=False)

    if report.contradictions_found == 0:
        return GateOutcome(
            True,
            "PASS",
            "no contradictions",
            0,
            report.consistency_score,
            0,
            False,
        )

    if mode == "human_required":
        return GateOutcome(
            False,
            "FAIL",
            f"{report.contradictions_found} contradictions - human review required "
            f"(LEGAL-NO-AUTOFIX); contested={report.most_contested[:3]}",
            1,
            report.consistency_score,
            report.contradictions_found,
            True,
        )

    if mode == "report":
        return GateOutcome(
            False,
            "FAIL",
            f"{report.contradictions_found} contradictions (report mode, no repair)",
            1,
            report.consistency_score,
            report.contradictions_found,
            False,
        )

    # auto_repair path already ran
    if report.unresolved > 0:
        return GateOutcome(
            False,
            "FAIL",
            f"auto_repair left {report.unresolved} unresolved",
            1,
            report.consistency_score,
            report.contradictions_found,
            False,
        )
    return GateOutcome(
        True,
        "PASS",
        f"auto_repaired {report.contradictions_repaired}",
        0,
        report.consistency_score,
        report.contradictions_found,
        False,
    )


def assert_beliefs_clean(store: WorldOracleStore, *, mode: Mode = "human_required") -> GateOutcome:
    out = gate_beliefs(store, mode=mode)
    if not out.ok:
        raise RuntimeError(f"{out.verdict}: {out.reason}")
    return out
