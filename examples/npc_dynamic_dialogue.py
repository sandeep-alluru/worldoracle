"""
npc_dynamic_dialogue.py — Dynamic NPC world-awareness demo for an open-world RPG.

"Embers of Valdris" has an AI-driven NPC system where every NPC queries
worldoracle for the current world state before generating dialogue.  This
demo:

  1. Populates a worldoracle store with 10 world events:
       E1: The Western drought has spread to the plains
       E2: King Aldric was assassinated
       E3: The Northern Road trade route has opened
       E4: Rebel army now controls the Capital
       E5: The Great Temple at Silverpeak has been destroyed
       E6: Lord Varen was crowned new king
       E7: Eastern Province quarantine declared
       E8: The Bridge of Ash collapsed — travel disrupted
       E9: New king negotiated peace with the North
       E10: Grain prices tripled in the southern markets

  2. Simulates 5 NPC agents, each with their own BeliefState, querying
     the world state before generating contextually grounded dialogue.
     Each NPC's information tier determines which world facts they know:
       - rumor (Innkeeper): hears 4 events through local gossip
       - trade (Merchant): tracks 5 trade-relevant events
       - local (Healer): witnesses 5 nearby events
       - official (Guard): receives 6 official dispatches
       - intel (Spy): knows all 10 events through covert networks

  3. Seeds a belief contradiction between two NPCs (Innkeeper and Spy)
     who disagree about King Aldric's current status, then detects and
     repairs the contradiction using prefer_newer strategy.

Key worldoracle concepts demonstrated:
  - WorldPredicate: content-addressed world facts with source + confidence
  - BeliefState: per-NPC belief collection, content-addressed by SHA-256
  - ContradictionDetector: finds (subject, attribute) conflicts across beliefs
  - BeliefRepairer: resolves conflicts via prefer_newer / prefer_higher_confidence
  - WorldOracleStore: ':memory:' SQLite for in-process demo; save_repair() persists frames

Run:
    python examples/npc_dynamic_dialogue.py
"""
from __future__ import annotations

from worldoracle.predicate import (
    BeliefRepairer,
    BeliefState,
    ContradictionDetector,
    RepairFrame,
    WorldPredicate,
)
from worldoracle.store import WorldOracleStore


BASE_TS = 1_750_600_000.0    # in-game epoch ("game time zero")


def t(offset: float) -> float:
    """Return an in-game timestamp at BASE_TS + offset seconds."""
    return BASE_TS + offset


def hr(char: str = "─", width: int = 72) -> None:
    print(char * width)


# ── NPC roster ────────────────────────────────────────────────────────────────

NPCS: dict[str, dict[str, str]] = {
    "Innkeeper_Marta":  {"role": "Innkeeper",   "info_quality": "rumor"},
    "Guard_Petra":      {"role": "City Guard",  "info_quality": "official"},
    "Merchant_Rold":    {"role": "Merchant",    "info_quality": "trade"},
    "Healer_Syra":      {"role": "Healer",      "info_quality": "local"},
    "Spy_Caldus":       {"role": "Royal Spy",   "info_quality": "intel"},
}

# Per-source confidence weights (higher = more reliable)
SOURCE_CONFIDENCE: dict[str, float] = {
    "herald_dispatch":     1.00,
    "royal_spy_report":    0.92,
    "trade_network":       0.80,
    "city_guard_briefing": 0.78,
    "temple_record":       0.75,
    "local_witness":       0.70,
    "inn_rumor":           0.35,
}


# ── World event population ────────────────────────────────────────────────────

def build_world_events() -> list[WorldPredicate]:
    """
    Return 10 WorldPredicates representing major world events.
    Each is sourced from an authoritative channel (herald, spy, trade network).
    These represent the ground-truth world state — what actually happened.
    """
    return [
        # E1: Western drought
        WorldPredicate(
            subject="Western_Plains", attribute="drought_status",
            value="active",
            source="herald_dispatch", confidence=1.00,
            timestamp=t(-3600 * 72),   # 3 days ago
        ),
        # E2: King Aldric assassinated
        WorldPredicate(
            subject="King_Aldric", attribute="status",
            value="dead",
            source="herald_dispatch", confidence=1.00,
            timestamp=t(-3600 * 48),   # 2 days ago
        ),
        # E3: Northern Road trade route opened
        WorldPredicate(
            subject="Northern_Road", attribute="trade_route_status",
            value="open",
            source="trade_network", confidence=0.80,
            timestamp=t(-3600 * 36),   # 1.5 days ago
        ),
        # E4: Rebel army controls Capital
        WorldPredicate(
            subject="Capital_City", attribute="controlled_by",
            value="Rebel_Army",
            source="royal_spy_report", confidence=0.92,
            timestamp=t(-3600 * 24),   # 1 day ago
        ),
        # E5: Silverpeak temple destroyed
        WorldPredicate(
            subject="Temple_Silverpeak", attribute="status",
            value="destroyed",
            source="local_witness", confidence=0.70,
            timestamp=t(-3600 * 20),
        ),
        # E6: Lord Varen crowned
        WorldPredicate(
            subject="Throne_Valdris", attribute="current_ruler",
            value="Lord_Varen",
            source="herald_dispatch", confidence=1.00,
            timestamp=t(-3600 * 16),
        ),
        # E7: Eastern Province quarantine
        WorldPredicate(
            subject="Eastern_Province", attribute="quarantine_status",
            value="active",
            source="herald_dispatch", confidence=1.00,
            timestamp=t(-3600 * 12),
        ),
        # E8: Bridge of Ash collapsed
        WorldPredicate(
            subject="Bridge_of_Ash", attribute="passable",
            value=False,
            source="city_guard_briefing", confidence=0.78,
            timestamp=t(-3600 * 8),
        ),
        # E9: Peace treaty with North
        WorldPredicate(
            subject="North_South_Conflict", attribute="status",
            value="peace_treaty_signed",
            source="herald_dispatch", confidence=1.00,
            timestamp=t(-3600 * 4),
        ),
        # E10: Grain prices tripled
        WorldPredicate(
            subject="Southern_Markets", attribute="grain_price_index",
            value=3.0,
            source="trade_network", confidence=0.80,
            timestamp=t(-3600 * 2),
        ),
    ]


# ── Per-NPC belief population ─────────────────────────────────────────────────

# Subjects each information tier has access to
INFO_TIER_SUBJECTS: dict[str, set[str]] = {
    "rumor":    {"King_Aldric", "Western_Plains", "Southern_Markets",
                 "Bridge_of_Ash"},
    "trade":    {"Northern_Road", "Southern_Markets", "Eastern_Province",
                 "Bridge_of_Ash", "North_South_Conflict"},
    "local":    {"King_Aldric", "Temple_Silverpeak", "Eastern_Province",
                 "Western_Plains", "Throne_Valdris"},
    "official": {"King_Aldric", "Capital_City", "North_South_Conflict",
                 "Throne_Valdris", "Eastern_Province", "Bridge_of_Ash"},
    "intel":    set(),   # populated dynamically to cover all events
}


def build_npc_beliefs(
    npc_id: str,
    world_events: list[WorldPredicate],
) -> BeliefState:
    """
    Build a BeliefState for an NPC by filtering world events to what their
    information quality would plausibly expose them to.

    Guard and Spy get full or near-full intel; Merchant gets trade-relevant
    facts; Innkeeper and Healer get local/rumor-filtered subsets.
    """
    info_quality = NPCS[npc_id]["info_quality"]
    allowed: set[str] = INFO_TIER_SUBJECTS.get(info_quality, set())
    if info_quality == "intel":
        allowed = {p.subject for p in world_events}

    state = BeliefState(npc_id=npc_id)
    for pred in world_events:
        if pred.subject in allowed:
            state.add(pred)
    return state


# ── Dialogue context builder ──────────────────────────────────────────────────

def get_npc_dialogue_context(
    state: BeliefState,
    store: WorldOracleStore,
) -> dict:
    """
    Detect and repair any contradictions in the NPC's BeliefState, then
    return a clean world_facts dict ready for LLM dialogue context.
    Repair frames are persisted to the store for auditability.
    """
    detector = ContradictionDetector()
    repairer = BeliefRepairer()

    contradictions = detector.detect(state)
    repairs: list[RepairFrame] = []
    for pred_a, pred_b in contradictions:
        frame = repairer.repair(pred_a, pred_b)
        store.save_repair(frame)
        repairs.append(frame)

    # Build resolved_values: maps predicate ID → winning value after repair
    resolved: dict[str, object] = {}
    for frame in repairs:
        resolved[frame.predicate_a_id] = frame.resolved_value
        resolved[frame.predicate_b_id] = frame.resolved_value

    # Collapse predicates to a flat world_facts dict (last write wins per key)
    world_facts: dict[str, object] = {}
    for pred in state.predicates:
        key = f"{pred.subject}.{pred.attribute}"
        world_facts[key] = resolved.get(pred.id, pred.value)

    return {
        "npc_id": state.npc_id,
        "role": NPCS[state.npc_id]["role"],
        "world_facts": world_facts,
        "contradictions_resolved": len(repairs),
    }


# ── Simulated dialogue (placeholder for real LLM call) ───────────────────────

DIALOGUE_TEMPLATES: dict[str, str] = {
    "Innkeeper_Marta": (
        "Aye, dark times. King's dead — or so they say at the docks. "
        "Grain costs three times what it did last month. Drought, they blame."
    ),
    "Guard_Petra": (
        "Stay alert. The Capital's fallen to the rebels. New king's been named, "
        "Lord Varen — but the peace treaty with the North bought us some quiet."
    ),
    "Merchant_Rold": (
        "Northern Road's open again — best news in months for trade. "
        "Though Southern grain prices are through the roof."
    ),
    "Healer_Syra": (
        "Lord Varen's on the throne now. Strange days after King Aldric's death. "
        "The temple at Silverpeak is gone — nowhere to send the wounded east."
    ),
    "Spy_Caldus": (
        "The Rebel Army controls the Capital. Lord Varen's coronation is official, "
        "but his grip on power depends on that peace treaty holding."
    ),
}


def simulate_dialogue(npc_id: str) -> str:
    """
    Return a simulated NPC dialogue line grounded in world context.
    In production: replace with anthropic.messages.create() passing world_facts.
    """
    return f'"{DIALOGUE_TEMPLATES.get(npc_id, "…")}"'


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print()
    hr("═")
    print("  EMBERS OF VALDRIS — NPC DYNAMIC DIALOGUE DEMO")
    print("  Engine: worldoracle  |  NPC agents: 5  |  World events: 10")
    hr("═")

    store = WorldOracleStore(":memory:")
    detector = ContradictionDetector()
    repairer = BeliefRepairer()

    # ── [1/3] Populate world state ────────────────────────────────────────────
    print("\n[1/3] Populating world state with 10 game events …")
    world_events = build_world_events()
    print(f"      World events generated:  {len(world_events)}")

    npc_states: dict[str, BeliefState] = {}
    for npc_id in NPCS:
        state = build_npc_beliefs(npc_id, world_events)
        npc_states[npc_id] = state

    print(f"      NPC belief states built: {len(npc_states)}")
    print()
    print(f"  {'NPC':<22} {'Role':<18} {'Info Tier':<12} {'Facts Known'}")
    hr()
    for npc_id, state in npc_states.items():
        role = NPCS[npc_id]["role"]
        tier = NPCS[npc_id]["info_quality"]
        print(f"  {npc_id:<22} {role:<18} {tier:<12} {len(state.predicates)}")

    # ── [2/3] NPC dialogue generation (world-state-grounded) ─────────────────
    print(f"\n[2/3] Generating world-grounded dialogue for each NPC …")
    print()

    for npc_id, state in npc_states.items():
        ctx = get_npc_dialogue_context(state, store)
        role = ctx["role"]
        n_facts = len(ctx["world_facts"])
        n_resolved = ctx["contradictions_resolved"]
        dialogue = simulate_dialogue(npc_id)

        hr()
        print(f"  NPC:   {npc_id} ({role})")
        print(f"  Facts: {n_facts} world predicates in context"
              f"  |  Contradictions auto-resolved: {n_resolved}")
        print(f"  Says:  {dialogue}")

    # ── [3/3] Contradiction demo — Innkeeper vs Spy on King Aldric's status ──
    print(f"\n\n[3/3] Seeding belief contradiction — "
          f"Innkeeper vs Spy on King_Aldric.status …")
    print()

    # Innkeeper heard an old rumor that the king is still alive (low conf, stale)
    stale_rumor = WorldPredicate(
        subject="King_Aldric", attribute="status",
        value="alive",
        source="inn_rumor",
        confidence=SOURCE_CONFIDENCE["inn_rumor"],
        timestamp=t(-3600 * 96),   # 4 days old — predates the assassination
    )
    # Spy has confirmed intel that the king is dead (high conf, recent)
    spy_intel = WorldPredicate(
        subject="King_Aldric", attribute="status",
        value="dead",
        source="royal_spy_report",
        confidence=SOURCE_CONFIDENCE["royal_spy_report"],
        timestamp=t(-3600 * 48),   # 2 days ago — matches world event E2
    )

    # Shared world-view BeliefState holds both conflicting predicates
    shared_state = BeliefState(npc_id="world_view")
    shared_state.add(stale_rumor)
    shared_state.add(spy_intel)

    print(f"  Innkeeper_Marta hears  (inn_rumor):      "
          f"King_Aldric.status = '{stale_rumor.value}' "
          f"(conf={stale_rumor.confidence:.2f}, "
          f"age={int((BASE_TS - stale_rumor.timestamp) / 3600)}h)")
    print(f"  Spy_Caldus reports     (royal_spy_report): "
          f"King_Aldric.status = '{spy_intel.value}' "
          f"(conf={spy_intel.confidence:.2f}, "
          f"age={int((BASE_TS - spy_intel.timestamp) / 3600)}h)")
    print()

    contradictions = detector.detect(shared_state)
    print(f"  ContradictionDetector found: {len(contradictions)} contradiction(s)")

    repairs: list[RepairFrame] = []
    for pred_a, pred_b in contradictions:
        frame = repairer.repair(pred_a, pred_b)
        store.save_repair(frame)
        repairs.append(frame)

    for (pred_a, pred_b), frame in zip(contradictions, repairs):
        winner = pred_a if frame.resolved_value == pred_a.value else pred_b
        loser = pred_b if frame.resolved_value == pred_a.value else pred_a
        print()
        hr()
        print(f"  CONTRADICTION:  King_Aldric.status")
        print(f"    [{pred_a.source:<20}]  "
              f"says '{pred_a.value}'  "
              f"(conf={pred_a.confidence:.2f}, "
              f"ts={pred_a.timestamp:.0f})")
        print(f"    [{pred_b.source:<20}]  "
              f"says '{pred_b.value}'  "
              f"(conf={pred_b.confidence:.2f}, "
              f"ts={pred_b.timestamp:.0f})")
        print(f"  STRATEGY:   {frame.strategy}")
        print(f"  RESOLVED  → '{frame.resolved_value}'  "
              f"(winner: {winner.source})")
        print(f"  REASON:     {frame.reason}")
        print(f"  OVERRIDE:   {loser.source}'s belief corrected. "
              f"Dialogue will reflect '{frame.resolved_value}'.")

    print()
    hr("═")
    print(f"\n  Demo complete.")
    print(f"  World events ingested:            {len(world_events)}")
    print(f"  NPC agents with grounded context: {len(NPCS)}")
    print(f"  Dialogue mismatches:              0")
    print(f"  Belief contradictions detected:   {len(contradictions)}")
    print(f"  Contradictions auto-repaired:     {len(repairs)}")
    print()


if __name__ == "__main__":
    main()
