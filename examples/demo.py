"""worldoracle demo — end-to-end example of contradiction detection and repair.

Run from repo root:
    python examples/demo.py
"""

from __future__ import annotations

from worldoracle import (
    BeliefRepairer,
    BeliefState,
    ContradictionDetector,
    WorldOracleStore,
    WorldPredicate,
    print_beliefs,
    print_repairs,
    to_json,
    to_markdown,
)


def main() -> None:
    """Run a complete worldoracle demonstration."""
    print("=" * 60)
    print("worldoracle Demo — NPC Belief Contradiction Detection")
    print("=" * 60)

    # ── 1. Build a belief state ───────────────────────────────────────────────
    print("\n1. Building NPC belief state for 'guard-1'...")
    state = BeliefState(npc_id="guard-1")

    # Quest giver told the guard the king is alive (earlier, lower confidence)
    state.add(
        WorldPredicate(
            subject="king",
            attribute="alive",
            value=True,
            source="quest-giver",
            confidence=0.7,
            timestamp=100.0,
        )
    )
    # Guard directly observed the king's death (later, higher confidence)
    state.add(
        WorldPredicate(
            subject="king",
            attribute="alive",
            value=False,
            source="observation",
            confidence=1.0,
            timestamp=200.0,
        )
    )
    # Consistent belief about bridge
    state.add(
        WorldPredicate(
            subject="bridge-3",
            attribute="passable",
            value=True,
            source="observation",
            confidence=0.9,
            timestamp=50.0,
        )
    )

    print_beliefs(state)

    # ── 2. Detect contradictions ──────────────────────────────────────────────
    print("\n2. Detecting contradictions...")
    detector = ContradictionDetector()
    contradictions = detector.detect(state)
    print(f"Found {len(contradictions)} contradiction(s)")
    for a, b in contradictions:
        print(f"  CONFLICT: {a.subject}.{a.attribute} = {a.value!r} vs {b.value!r}")

    # ── 3. Repair contradictions ──────────────────────────────────────────────
    print("\n3. Repairing contradictions...")
    repairer = BeliefRepairer()
    repairs = []
    for a, b in contradictions:
        frame = repairer.repair(a, b)
        repairs.append(frame)
        print(f"  Strategy: {frame.strategy}")
        print(f"  Resolved value: {frame.resolved_value!r}")
        print(f"  Reason: {frame.reason}")

    print_repairs(repairs)

    # ── 4. Store to SQLite ────────────────────────────────────────────────────
    print("\n4. Persisting to SQLite (:memory:)...")
    store = WorldOracleStore(":memory:")
    for pred in state.predicates:
        store.save_predicate("guard-1", pred)
    for repair in repairs:
        store.save_repair(repair)

    loaded_state = store.get_belief_state("guard-1")
    print(f"  Loaded {len(loaded_state.predicates)} predicate(s) for guard-1")
    store.close()

    # ── 5. Formatters ─────────────────────────────────────────────────────────
    print("\n5. JSON output:")
    json_str = to_json(state, repairs=repairs)
    print(json_str[:300] + "..." if len(json_str) > 300 else json_str)

    print("\n6. Markdown output:")
    md = to_markdown([state])
    print(md[:400] + "..." if len(md) > 400 else md)

    print("\n" + "=" * 60)
    print("Demo complete — worldoracle is working correctly!")
    print("=" * 60)


if __name__ == "__main__":
    main()
