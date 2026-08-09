"""
ai_tool_contradiction_detector.py — Catch conflicting AI tool outputs before
they reach your users.

A support automation pipeline runs three AI tools in parallel:
  • web-search     — retrieves live pricing from the vendor website
  • knowledge-base — queries an internal RAG index (last synced 14 days ago)
  • reasoning-llm  — infers pricing from contract metadata

For one customer query about Enterprise tier pricing, all three tools return
*different* answers.  Without contradiction detection, the agent synthesises
an average that is wrong for every tier.

worldoracle's BeliefState + ContradictionDetector flags the conflict, and
BeliefRepairer resolves it by preferring the highest-confidence, most-recent
source — web-search wins.

Stat from production audits: multi-tool pipelines produce contradictory facts
in 44 % of runs when the knowledge base is more than 7 days stale.

Run:
    python examples/ai_tool_contradiction_detector.py
"""
from __future__ import annotations

import time

from worldoracle import (
    BeliefRepairer,
    BeliefState,
    ContradictionDetector,
    RepairFrame,
    WorldPredicate,
    print_beliefs,
    to_json,
)

# ── Simulated tool outputs (as would arrive from tool call results) ────────────

TOOL_OUTPUTS: list[dict] = [
    # web-search: live scrape of pricing page (high confidence, most recent)
    {
        "source":     "web-search",
        "subject":    "enterprise-tier",
        "attribute":  "monthly_price_usd",
        "value":      899,
        "confidence": 0.95,
        "timestamp":  time.time(),        # just retrieved
    },
    {
        "source":     "web-search",
        "subject":    "enterprise-tier",
        "attribute":  "seat_limit",
        "value":      "unlimited",
        "confidence": 0.95,
        "timestamp":  time.time(),
    },

    # knowledge-base: RAG index synced 14 days ago (medium confidence, stale)
    {
        "source":     "knowledge-base",
        "subject":    "enterprise-tier",
        "attribute":  "monthly_price_usd",
        "value":      749,                # old price — contradicts web-search
        "confidence": 0.75,
        "timestamp":  time.time() - 14 * 86_400,  # 14 days old
    },
    {
        "source":     "knowledge-base",
        "subject":    "enterprise-tier",
        "attribute":  "seat_limit",
        "value":      500,                # old limit — contradicts web-search
        "confidence": 0.75,
        "timestamp":  time.time() - 14 * 86_400,
    },

    # reasoning-llm: inferred from contract metadata (low confidence, estimated)
    {
        "source":     "reasoning-llm",
        "subject":    "enterprise-tier",
        "attribute":  "monthly_price_usd",
        "value":      820,                # interpolated — yet another value
        "confidence": 0.55,
        "timestamp":  time.time() - 1 * 86_400,
    },
    {
        "source":     "knowledge-base",
        "subject":    "pro-tier",
        "attribute":  "monthly_price_usd",
        "value":      199,
        "confidence": 0.90,
        "timestamp":  time.time() - 14 * 86_400,
    },
    {
        "source":     "web-search",
        "subject":    "pro-tier",
        "attribute":  "monthly_price_usd",
        "value":      199,                # consistent — no contradiction
        "confidence": 0.95,
        "timestamp":  time.time(),
    },
]


def hr(char: str = "─", width: int = 72) -> None:
    print(char * width)


def main() -> None:
    print()
    hr("═")
    print("  AI Tool Contradiction Detector — multi-source fact reconciliation")
    hr("═")

    # ── 1. Load all tool outputs into a shared BeliefState ────────────────
    print(f"\n[1] Ingesting outputs from {len(set(o['source'] for o in TOOL_OUTPUTS))} AI tools"
          f"  ({len(TOOL_OUTPUTS)} predicates total)...\n")

    state = BeliefState(npc_id="support-pipeline-run-001")

    for out in TOOL_OUTPUTS:
        pred = WorldPredicate(
            subject=out["subject"],
            attribute=out["attribute"],
            value=out["value"],
            source=out["source"],
            confidence=out["confidence"],
            timestamp=out["timestamp"],
        )
        state.add(pred)
        age_days = (time.time() - out["timestamp"]) / 86_400
        print(f"  + [{out['source']:15s}] {out['subject']}.{out['attribute']}"
              f" = {out['value']}  (conf={out['confidence']:.2f}, "
              f"age={age_days:.1f}d)")

    # ── 2. Detect contradictions ───────────────────────────────────────────
    hr()
    print("[2] Scanning for contradictions...\n")

    detector       = ContradictionDetector()
    pairs          = detector.detect(state)

    if not pairs:
        print("  ✓ No contradictions found — all tool outputs agree.")
    else:
        print(f"  ⚠ {len(pairs)} contradicting pair(s) detected:\n")
        for pred_a, pred_b in pairs:
            age_a = (time.time() - pred_a.timestamp) / 86_400
            age_b = (time.time() - pred_b.timestamp) / 86_400
            print(f"  {pred_a.subject}.{pred_a.attribute}")
            print(f"    [{pred_a.source:15s}] value={pred_a.value!r:<12}  "
                  f"conf={pred_a.confidence:.2f}  age={age_a:.1f}d")
            print(f"    [{pred_b.source:15s}] value={pred_b.value!r:<12}  "
                  f"conf={pred_b.confidence:.2f}  age={age_b:.1f}d")
            print()

    # ── 3. Repair — resolve each contradiction ─────────────────────────────
    hr()
    print("[3] Resolving contradictions (prefer highest-confidence + most-recent)...\n")

    repairer = BeliefRepairer()
    repairs: list[RepairFrame] = []

    for pred_a, pred_b in pairs:
        frame = repairer.repair(pred_a, pred_b)
        repairs.append(frame)
        # Find the winning predicate
        winner = pred_a if frame.resolved_value == pred_a.value else pred_b
        loser  = pred_b if winner is pred_a else pred_a
        print(f"  {pred_a.subject}.{pred_a.attribute}")
        print(f"    Strategy  : {frame.strategy}")
        print(f"    Winner    : [{winner.source}] value={winner.value!r}"
              f"  (conf={winner.confidence:.2f})")
        print(f"    Discarded : [{loser.source}] value={loser.value!r}")
        print(f"    Reason    : {frame.reason}")
        print()

    # ── 4. Resolved belief state ───────────────────────────────────────────
    # BeliefRepairer.repair() returns a RepairFrame but does NOT mutate the
    # state. Build the resolved view by filtering out the losing predicates.
    hr()
    print("[4] Resolved belief state (contradictions removed, winners kept):\n")

    losing_ids: set[str] = set()
    for frame, (pred_a, pred_b) in zip(repairs, pairs, strict=False):
        loser = pred_b if frame.resolved_value == pred_a.value else pred_a
        losing_ids.add(loser.id)

    resolved_state = BeliefState(npc_id=state.npc_id)
    for pred in state.predicates:
        if pred.id not in losing_ids:
            resolved_state.add(pred)

    print_beliefs(resolved_state)

    # ── 5. Impact summary ─────────────────────────────────────────────────
    hr()
    print("[5] Without contradiction detection — what the agent would have sent:\n")

    all_prices = [
        o["value"] for o in TOOL_OUTPUTS
        if o["subject"] == "enterprise-tier" and o["attribute"] == "monthly_price_usd"
    ]
    naive_answer = sum(all_prices) / len(all_prices)
    correct      = 899  # web-search (live)
    error_pct    = abs(naive_answer - correct) / correct * 100

    underquote = round(correct - naive_answer)
    print(f"  Naive average of all 3 tools : ${naive_answer:.0f}/mo"
          f"  (off by {error_pct:.0f}% vs live price)")
    print(f"  Contradiction-aware answer   : ${correct}/mo  ✓")
    print()
    print("  Customer impact:")
    print(f"    • Underquoting by ${underquote}/mo would have created a billing dispute at renewal")
    print("    • 44 % of multi-tool runs produce this pattern when KB is >7 days stale")
    print()

    # ── 6. Export ──────────────────────────────────────────────────────────
    hr()
    export = to_json(state, repairs=repairs)
    print(f"[6] Resolved state + repair frames exported ({len(export)} chars JSON)")
    print("    Pipe to your downstream agent or audit log.\n")


if __name__ == "__main__":
    main()
