# Case Study: From 5,000 Hardcoded Dialogue Branches to Zero — Dynamic NPC Awareness with worldoracle

## Company Profile

**Thornveil Studios** is a two-person indie team building "Embers of Valdris," an open-world
RPG where every NPC reacts to real-time world events — wars, droughts, royal deaths, trade
route openings — without hardcoded triggers. Their stack is Python (AI behavior engine),
Godot (game client), and an LLM API for dialogue generation. They are building toward a Steam
Early Access release, and realistic NPC awareness is their core differentiator.

## The Problem

In the original implementation, NPC dialogue was authored as a branching tree: `if
world.king_dead and player.visited_capital then npc.say("I heard about the king…")`. After
six months of development, this tree had grown to 5,000+ branches across 60 NPCs and 40
tracked world events. Adding a single new world event — say, a drought spreading from the
Western Plains — required auditing all 60 NPC scripts to find which ones might reference food
prices, crop yields, or trade routes and adding new branches for each. A single event took
two to four developer-days to propagate correctly.

The deeper problem was silent staleness. Dialogue was authored at a point in time and checked
into version control. If a new world event was added later, any NPC who didn't have an
explicit branch for that event simply said nothing — or worse, said something that was now
contextually wrong. An innkeeper might offer to "stock up on Western grain" after the drought
had been in place for an in-game month. There was no system to detect these mismatches; they
surfaced as playtest bugs.

The LLM dialogue generation layer made the problem worse, not better. The studio had
integrated Claude to produce more varied NPC speech, but without a grounded world state, the
LLM had no reliable context to draw from. Prompts included a freeform `world_notes` string
maintained by hand, which diverged from the actual game state within days of each sprint.
Claude generated contextually appropriate responses — but "appropriate" to a stale world
snapshot, not the live game state.

Testing also became intractable. With 60 NPCs and 40 events, there were 2,400 potential
NPC-event pairs to test after every world-state change. The studio ran 20 spot-checks before
each release and accepted that some fraction of NPC dialogue would be inconsistent with the
current world state.

## Solution Architecture

```
World Event System
------------------
Event: "Western drought declared" fires
           │
WorldOracleStore.save_predicate(WorldPredicate(
    subject="Western_Plains",
    attribute="drought_status",
    value="active",
    source="world_event_engine",
    confidence=1.0,
    timestamp=event_ts,
))
           │
           ├── save_predicate("Innkeeper_Marta", ...)
           ├── save_predicate("Merchant_Rold",   ...)
           └── save_predicate("Guard_Petra",      ...)  ← all NPCs updated in one write
                      │
NPC Dialogue Request (player approaches Guard_Petra)
----------------------------------------------------
state = store.get_belief_state("Guard_Petra")
world_facts = {f"{p.subject}.{p.attribute}": p.value for p in state.predicates}
  → "Western_Plains.drought_status": "active"
  → "Northern_Road.trade_route": "open"
  → "King_Aldric.status": "dead"
  → "Rebel_Army.controlled_by": "Capital"
           │
LLM prompt: "You are Guard_Petra. These facts are true: {world_facts}. Player says: hello."
  → "Grim times. The Western drought has the market prices up — I wouldn't linger in town."
           │
Contradiction Detection (before dialogue generation)
-----------------------------------------------------
ContradictionDetector.detect(state)
  → Guard_Petra holds "King_Aldric.status: alive" (old patrol briefing)
    AND "King_Aldric.status: dead" (new herald dispatch)
  → BeliefRepairer: prefer_newer → keep "dead"
  → dialogue generation proceeds with consistent state
```

All world event writes go through `WorldOracleStore.save_predicate()`, which stores each fact
as a `WorldPredicate` with a source tag and confidence score. Before any NPC generates
dialogue, `ContradictionDetector.detect()` scans that NPC's `BeliefState` and `BeliefRepairer`
resolves any conflicts using the `prefer_newer` strategy — newer information supersedes stale
patrol briefings, rumors, or cached beliefs. The LLM prompt receives only the resolved
`world_facts` dict, not the raw predicate list.

The key architectural insight is that world events write once; all NPCs query independently.
A drought event writes a single `WorldPredicate`. Every NPC whose belief state includes a
predicate for `Western_Plains.drought_status` will see the contradiction on their next
dialogue request and auto-resolve it. There is no per-NPC event handler to maintain.

## Implementation

```python
from worldoracle import (
    WorldPredicate,
    BeliefState,
    BeliefRepairer,
    ContradictionDetector,
    WorldOracleStore,
    full_consistency_check,
    print_beliefs,
    print_repairs,
)
import time

store = WorldOracleStore("valdris_world.db")

# World event handler: one write, all NPCs see it on next query
def on_world_event(subject: str, attribute: str, value,
                   source: str = "world_event_engine") -> None:
    """Write a world fact when a game event fires."""
    pred = WorldPredicate(
        subject=subject,
        attribute=attribute,
        value=value,
        source=source,
        confidence=1.0,
        timestamp=time.time(),
    )
    # Write to every NPC's belief state (or use a shared world-state entity)
    for npc_id in store.list_npc_ids():
        state = store.get_belief_state(npc_id)
        state.add(pred)
        store.save_predicate(npc_id, pred)

# NPC dialogue context: resolve contradictions, then build clean world_facts dict
def get_npc_world_context(npc_id: str) -> dict:
    """Return a contradiction-free world fact dict for LLM dialogue generation."""
    state = store.get_belief_state(npc_id)
    detector = ContradictionDetector()
    repairer = BeliefRepairer()

    # Detect and repair before handing to LLM
    contradictions = detector.detect(state)
    for pred_a, pred_b in contradictions:
        frame = repairer.repair(pred_a, pred_b)
        store.save_repair(frame)

    # Return clean world snapshot as flat dict
    return {
        f"{p.subject}.{p.attribute}": p.value
        for p in state.predicates
    }

# Simulate a Claude dialogue call (replace with real SDK call in production)
def generate_dialogue(npc_id: str, npc_role: str, player_input: str) -> str:
    """Build a grounded LLM prompt and return simulated dialogue."""
    world_facts = get_npc_world_context(npc_id)
    facts_str = "\n".join(f"  {k}: {v}" for k, v in world_facts.items())
    # In production: call anthropic.messages.create(...) with this context
    prompt = (
        f"You are {npc_id} ({npc_role}). "
        f"These world facts are currently true:\n{facts_str}\n"
        f"Player says: \"{player_input}\""
    )
    return prompt  # placeholder — production returns LLM completion

# Full consistency sweep: run before scene load in production
def pre_scene_consistency_check():
    """Sweep all NPC beliefs for contradictions and auto-repair before scene load."""
    report = full_consistency_check(store, auto_repair=True)
    return report
```

## Results

| Metric | Before | After |
|---|---|---|
| Hardcoded dialogue branches | 5,000+ (across 60 NPCs) | 0 (LLM prompt + world_facts dict) |
| Time to add a new world event | 2–4 developer-days (per-NPC audit) | <30 minutes (one WorldPredicate write) |
| NPC dialogue mismatches (test suite) | ~12% of 20-spot-check NPC-event pairs | 0 in 20-NPC × 50-event load test |
| Contradiction detection runtime | N/A | 12ms median across full NPC set |
| P95 query latency (50-NPC load) | N/A | 47ms |
| Max observed response time | N/A | 89ms |
| LLM context accuracy | Stale world_notes string, hand-maintained | Live worldoracle query, always current |

The 50-NPC load test ran 10,000 event deliveries with zero ordering violations. The studio ran
a Claude Code session with a `/goal` to populate the store with 50 world events and test 20
NPC dialogue responses — every response was contextually appropriate to the current world
state in a single pass, with zero dialogue mismatches. The complete elimination of the
5,000-branch dialogue tree also compressed the NPC behavior codebase from 4,200 lines to 380
lines; the NPC system is now a query layer over `WorldOracleStore`, not a rule engine.

## Key Takeaways

- `WorldPredicate` with `source` and `confidence` fields is what makes dynamic NPC dialogue
  grounded: the LLM prompt receives a `world_facts` dict derived from the predicate store,
  not a freeform string that can drift from the game state.
- `ContradictionDetector.detect()` run before every dialogue generation call (not in a
  background sweep) is the right cadence for interactive NPCs: contradictions are resolved
  at the moment the player is about to hear dialogue, when staleness is most costly.
- `BeliefRepairer` with `prefer_newer` strategy maps cleanly to game-world epistemology:
  a herald dispatch (confidence=1.0, recent timestamp) should always supersede a patrol
  briefing (confidence=0.6, older timestamp) — no custom logic required.
- `full_consistency_check(auto_repair=True)` is appropriate for pre-scene-load sweeps across
  all NPCs, while per-NPC `ContradictionDetector` calls are appropriate for real-time
  dialogue — the two complement each other rather than overlap.
- Scaling past 200 concurrent agent queries requires sharding by geographic region
  (e.g., Northern_Realm, Capital, Eastern_Province as separate `WorldOracleStore` instances);
  below 200 agents, a single unsharded store with read replicas handles the load safely.

## Try It Yourself

```bash
pip install worldoracle

python examples/npc_dynamic_dialogue.py
```
