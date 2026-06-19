"""
rpg_npc_world.py — NPC belief consistency audit for an open-world RPG.

"Chronicles of Aethermoor" has 50 NPCs that independently learn about world
events and update their beliefs.  worldoracle audits all NPC beliefs, finds
contradictions (NPCs who disagree about the same fact), repairs them using
the highest-confidence, most-recent source, and prints a world-state report.

Key events in the game world:
  E1: King Aldric was assassinated
  E2: War broke out between the North and South
  E3: Plague spread to the Eastern Province
  E4: Rebel army captured the capital city
  E5: Lord Varen was crowned the new king
  E6: The Great Bridge collapsed

Run:
    python examples/rpg_npc_world.py
"""
from __future__ import annotations

import time
from collections import defaultdict

from worldoracle.predicate import (
    BeliefRepairer,
    BeliefState,
    ContradictionDetector,
    WorldPredicate,
)
from worldoracle.store import WorldOracleStore


BASE_TS = 1_750_300_000.0    # "game time" epoch


def t(offset: float) -> float:
    return BASE_TS + offset


def hr(char: str = "─", width: int = 72) -> None:
    print(char * width)


# ── NPC definitions ───────────────────────────────────────────────────────────

# The 8 named NPCs we model in detail (rest are background population)
NPCS = {
    "Innkeeper_Rowan":    {"role": "Innkeeper",     "info_quality": "rumor"},
    "Blacksmith_Doran":   {"role": "Blacksmith",    "info_quality": "rumor"},
    "Guard_Captain_Mira": {"role": "Guard Captain", "info_quality": "local"},
    "Merchant_Sable":     {"role": "Merchant",      "info_quality": "trade"},
    "Priest_Aldon":       {"role": "Priest",        "info_quality": "local"},
    "Healer_Yenna":       {"role": "Healer",        "info_quality": "local"},
    "Spy_Caldus":         {"role": "Spy",           "info_quality": "intel"},
    "Herald_Oryn":        {"role": "Herald",        "info_quality": "official"},
}


# ── Belief population ─────────────────────────────────────────────────────────

def populate_beliefs(store: WorldOracleStore) -> BeliefState:
    """
    Add 20+ predicates to a shared BeliefState representing what the NPC
    collective believes about the game world.  Contradictions are intentionally
    seeded for events E1, E2, E3, E4, and E5.

    All predicates for all NPCs go into a single shared BeliefState (npc_id="world")
    so the contradiction detector can compare cross-NPC beliefs.
    """
    state = BeliefState(npc_id="world_state")
    preds: list[WorldPredicate] = []

    # ── E1: King Aldric alive/dead ────────────────────────────────────────
    # Innkeeper heard a rumor he's alive (low confidence, old info)
    preds.append(WorldPredicate(
        subject="King_Aldric", attribute="is_alive",
        value=True,
        source="Innkeeper_Rowan",
        confidence=0.35,
        timestamp=t(-3600 * 5),     # 5 hours old
    ))
    # Spy confirmed he was assassinated (high confidence, recent intel)
    preds.append(WorldPredicate(
        subject="King_Aldric", attribute="is_alive",
        value=False,
        source="Spy_Caldus",
        confidence=0.90,
        timestamp=t(-3600 * 2),     # 2 hours old
    ))
    # Herald has official confirmation (certain, very recent)
    preds.append(WorldPredicate(
        subject="King_Aldric", attribute="is_alive",
        value=False,
        source="Herald_Oryn",
        confidence=1.00,
        timestamp=t(-3600 * 0.5),   # 30 min old
    ))
    # Blacksmith heard he was just injured, not dead
    preds.append(WorldPredicate(
        subject="King_Aldric", attribute="is_alive",
        value=True,
        source="Blacksmith_Doran",
        confidence=0.25,
        timestamp=t(-3600 * 6),
    ))

    # ── E1 follow-on: cause of death ──────────────────────────────────────
    preds.append(WorldPredicate(
        subject="King_Aldric", attribute="cause_of_death",
        value="poisoned",
        source="Spy_Caldus",
        confidence=0.85,
        timestamp=t(-3600 * 2),
    ))
    preds.append(WorldPredicate(
        subject="King_Aldric", attribute="cause_of_death",
        value="stabbed",
        source="Innkeeper_Rowan",
        confidence=0.30,
        timestamp=t(-3600 * 4),
    ))

    # ── E2: War status ────────────────────────────────────────────────────
    # Guard Captain knows war broke out (local official knowledge)
    preds.append(WorldPredicate(
        subject="North_South_War", attribute="active",
        value=True,
        source="Guard_Captain_Mira",
        confidence=0.95,
        timestamp=t(-3600 * 1),
    ))
    # Healer thinks it's just border skirmishes, not full war
    preds.append(WorldPredicate(
        subject="North_South_War", attribute="active",
        value=False,
        source="Healer_Yenna",
        confidence=0.50,
        timestamp=t(-3600 * 3),
    ))

    # ── E3: Plague location ───────────────────────────────────────────────
    # Merchant heard plague is in Eastern Province
    preds.append(WorldPredicate(
        subject="Plague", attribute="location",
        value="Eastern_Province",
        source="Merchant_Sable",
        confidence=0.70,
        timestamp=t(-3600 * 2),
    ))
    # Priest believes it's in the Capital too (more recent sermon)
    preds.append(WorldPredicate(
        subject="Plague", attribute="location",
        value="Capital",
        source="Priest_Aldon",
        confidence=0.60,
        timestamp=t(-3600 * 1),
    ))
    # Herald: plague confirmed to Eastern Province only (official quarantine)
    preds.append(WorldPredicate(
        subject="Plague", attribute="location",
        value="Eastern_Province",
        source="Herald_Oryn",
        confidence=1.00,
        timestamp=t(-1800),
    ))

    # ── E4: Capital control ───────────────────────────────────────────────
    # Spy: rebel army holds the capital
    preds.append(WorldPredicate(
        subject="Capital_City", attribute="controlled_by",
        value="Rebel_Army",
        source="Spy_Caldus",
        confidence=0.88,
        timestamp=t(-3600),
    ))
    # Guard Captain: capital is still in Royal hands (outdated)
    preds.append(WorldPredicate(
        subject="Capital_City", attribute="controlled_by",
        value="Royal_Guard",
        source="Guard_Captain_Mira",
        confidence=0.60,
        timestamp=t(-3600 * 4),
    ))
    # Herald: rebel army confirmed (official dispatch received)
    preds.append(WorldPredicate(
        subject="Capital_City", attribute="controlled_by",
        value="Rebel_Army",
        source="Herald_Oryn",
        confidence=1.00,
        timestamp=t(-1200),
    ))

    # ── E5: New king ──────────────────────────────────────────────────────
    # Herald: Lord Varen crowned (official)
    preds.append(WorldPredicate(
        subject="Throne_Aethermoor", attribute="current_ruler",
        value="Lord_Varen",
        source="Herald_Oryn",
        confidence=1.00,
        timestamp=t(-900),
    ))
    # Merchant heard it's Lady Serath (false rumor from trade route)
    preds.append(WorldPredicate(
        subject="Throne_Aethermoor", attribute="current_ruler",
        value="Lady_Serath",
        source="Merchant_Sable",
        confidence=0.40,
        timestamp=t(-3600 * 3),
    ))
    # Innkeeper heard "some lord" took over, thinks it might be Varen
    preds.append(WorldPredicate(
        subject="Throne_Aethermoor", attribute="current_ruler",
        value="Lord_Varen",
        source="Innkeeper_Rowan",
        confidence=0.55,
        timestamp=t(-3600 * 2),
    ))

    # ── E6: Great Bridge (no contradiction — everyone agrees) ─────────────
    preds.append(WorldPredicate(
        subject="Great_Bridge", attribute="status",
        value="collapsed",
        source="Guard_Captain_Mira",
        confidence=1.00,
        timestamp=t(-7200),
    ))
    preds.append(WorldPredicate(
        subject="Great_Bridge", attribute="passable",
        value=False,
        source="Merchant_Sable",
        confidence=0.95,
        timestamp=t(-5400),
    ))

    # ── Non-conflicting world facts ───────────────────────────────────────
    preds.append(WorldPredicate(
        subject="Eastern_Province", attribute="under_quarantine",
        value=True,
        source="Herald_Oryn",
        confidence=1.00,
        timestamp=t(-1800),
    ))
    preds.append(WorldPredicate(
        subject="Rebel_Army", attribute="leader",
        value="Commander_Dresh",
        source="Spy_Caldus",
        confidence=0.92,
        timestamp=t(-3600),
    ))

    for p in preds:
        state.add(p)
        store.save_predicate("world_state", p)

    return state


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print()
    hr("═")
    print("  CHRONICLES OF AETHERMOOR — WORLD STATE AUDIT")
    print(f"  System: NPC Belief Engine | Powered by: worldoracle")
    hr("═")

    store = WorldOracleStore(":memory:")
    detector = ContradictionDetector()
    repairer = BeliefRepairer()

    print("\n[1/3] Populating NPC belief predicates …")
    state = populate_beliefs(store)
    print(f"      NPCs modelled:         {len(NPCS)} named + background population")
    print(f"      Total predicates:      {len(state.predicates)}")

    print("\n[2/3] Running contradiction detection …")
    contradictions = detector.detect(state)
    print(f"      Contradictions found:  {len(contradictions)}")

    print("\n[3/3] Running belief repair …")
    repairs = []
    for pred_a, pred_b in contradictions:
        frame = repairer.repair(pred_a, pred_b)
        store.save_repair(frame)
        repairs.append((pred_a, pred_b, frame))
    print(f"      Repairs generated:     {len(repairs)}")

    hr()

    # Count corrections per source (NPC)
    corrections_by_source: dict[str, int] = defaultdict(int)
    for pred_a, pred_b, frame in repairs:
        # The "loser" (overridden belief) contributed an incorrect belief
        loser = pred_a if frame.resolved_value == pred_b.value else pred_b
        corrections_by_source[loser.source] += 1

    top_corrected = sorted(corrections_by_source.items(), key=lambda x: -x[1])[:5]
    top_str = ", ".join(f"{src} ({n} corrections)" for src, n in top_corrected)

    print()
    print(f"  WORLD STATE AUDIT: {len(state.predicates)} predicates checked, "
          f"{len(contradictions)} contradictions found, "
          f"{len(repairs)} repaired.")
    print(f"  NPCs with inconsistent beliefs: {top_str}")
    hr()

    # Show all contradiction + repair details
    print("\n  CONTRADICTION REPORT:")
    print()

    subjects_seen: set[str] = set()
    for pred_a, pred_b, frame in repairs:
        key = f"{pred_a.subject}:{pred_a.attribute}"
        subjects_seen.add(key)
        winner_pred = pred_a if frame.resolved_value == pred_a.value else pred_b
        loser_pred = pred_b if frame.resolved_value == pred_a.value else pred_a

        print(f"  Subject:   {pred_a.subject}.{pred_a.attribute}")
        print(f"  Conflict:  [{pred_a.source}] says '{pred_a.value}' "
              f"(confidence={pred_a.confidence:.2f}, "
              f"age={int((BASE_TS - pred_a.timestamp)/60)} min old)")
        print(f"             [{pred_b.source}] says '{pred_b.value}' "
              f"(confidence={pred_b.confidence:.2f}, "
              f"age={int((BASE_TS - pred_b.timestamp)/60)} min old)")
        print(f"  Strategy:  {frame.strategy}")
        print(f"  RESOLVED → '{frame.resolved_value}'  (from: {winner_pred.source})")
        print(f"  Reason:    {frame.reason}")
        print(f"  Override:  {loser_pred.source}'s belief corrected.")
        print()

    hr()
    print("\n  BEFORE / AFTER — Two representative contradictions:")
    print()

    # Before/after for King Aldric is_alive
    print("  ── King_Aldric.is_alive ──")
    print("  BEFORE repair (4 conflicting beliefs):")
    for p in state.predicates:
        if p.subject == "King_Aldric" and p.attribute == "is_alive":
            print(f"    • [{p.source}] is_alive={p.value} "
                  f"(conf={p.confidence:.2f})")
    king_repair = next(
        (r for a, b, r in repairs
         if a.subject == "King_Aldric" and a.attribute == "is_alive"),
        None,
    )
    if king_repair:
        print(f"  AFTER repair:")
        print(f"    • King_Aldric.is_alive = {king_repair.resolved_value}")
        print(f"    • Strategy: {king_repair.strategy}")
        print(f"    • {king_repair.reason}")
    print()

    # Before/after for Capital_City controlled_by
    print("  ── Capital_City.controlled_by ──")
    print("  BEFORE repair (3 conflicting beliefs):")
    for p in state.predicates:
        if p.subject == "Capital_City" and p.attribute == "controlled_by":
            print(f"    • [{p.source}] controlled_by={p.value} "
                  f"(conf={p.confidence:.2f})")
    cap_repair = next(
        (r for a, b, r in repairs
         if a.subject == "Capital_City" and a.attribute == "controlled_by"),
        None,
    )
    if cap_repair:
        print(f"  AFTER repair:")
        print(f"    • Capital_City.controlled_by = {cap_repair.resolved_value}")
        print(f"    • Strategy: {cap_repair.strategy}")
        print(f"    • {cap_repair.reason}")

    print()
    hr("═")
    print(f"\n  Audit complete. World state is now consistent.")
    print(f"  All NPC beliefs reconciled and stored. Game engine can proceed.")
    print()


if __name__ == "__main__":
    main()
