# Case Study: Eliminating Immersion-Breaking NPC Contradictions in a Narrative Game

## Company Profile

**Narrative Forge** is a narrative game studio with 18 engineers building an AI-driven story
game with a hand-authored branching narrative and 300+ autonomous NPCs. The game's central
mechanic is that the world state changes based on player decisions: towns can be destroyed,
rulers can die or be deposed, alliances shift, and characters hold beliefs about these events
that inform their dialogue. Their stack is Python (AI behavior engine), Unity (game client),
and an LLM API (dialogue generation). They are building toward a 50,000-player Early Access
launch.

## The Problem

As the game world grew more complex — 300 NPCs, 80 tracked world events, 12 major story
chapters — NPC belief inconsistencies became a persistent and worsening bug category. An NPC
would refer to a fact that was no longer true in the current world state:

- A town merchant says "Welcome to Thornwood, finest market in the region!" when Thornwood
  burned down in Chapter 4.
- A guard captain asks the player "Have you spoken to Lord Aldric? He's always at the
  manor this time of day," when Lord Aldric died in a story event 3 chapters earlier.
- A healer NPC offers to "send word to the temple at Silverpeak" when Silverpeak had been
  occupied by enemies since Chapter 6.

These contradictions were the top reported bug category in playtesting, accounting for 34% of
all QA bug reports. Finding them manually was expensive: a QA reviewer had to play through the
relevant story path, reach the specific world state, and then visit the NPC to observe the
dialogue. A single NPC inconsistency took 45–90 minutes to reproduce and report.

The technical root cause was fragmented belief state management. NPC beliefs were stored as
Python dicts in 300 separate NPC initialization scripts. When a major story event fired, an
event handler updated a central `world_state` dict, but propagating that change to the 300
NPC belief dicts required manually writing update logic for each affected NPC. Writers
frequently forgot to update NPCs who weren't directly involved in a story event but whose
dialogue referenced the affected fact.

Additionally, writers had no way to query "what did NPC Elara believe at the start of Chapter 3
when we wrote her dialogue?" — a common question when debugging inconsistent dialogue written
months earlier. The temporal dimension of NPC beliefs was completely untracked.

## Solution Architecture

```
Story Event System
------------------
Event: "Thornwood burns" fires
           │
WorldOracleStore.save_predicate(WorldPredicate(
    npc_id="all_thornwood_npcs",
    subject="thornwood",
    attribute="status",
    value="destroyed",
    source="story_event_ch4",
    confidence=1.0,
    timestamp=chapter4_ts,
))
           │
Scene Load (on every area transition)
--------------------------------------
full_consistency_check(store, auto_repair=True)
  → ContradictionDetector finds: "thornwood.status: active vs destroyed"
  → BeliefRepairer: prefer_higher_confidence → keep "destroyed"
  → 12ms runtime
           │
NPC Dialogue Generation
-----------------------
npc_belief = store.get_belief_state("merchant_07")
dialogue_context = npc_belief.predicates  → fed to LLM as world context
  (LLM now knows: thornwood=destroyed, lord_aldric=dead, etc.)
           │
Temporal Belief Query (writer QA tool)
---------------------------------------
temporal_store.get_belief_at("thornwood", "status", chapter3_timestamp)
  → "active" (Thornwood was still standing in Chapter 3)
  → writer confirms dialogue was correct when written
  → bug is in event handler, not the dialogue
```

All NPC beliefs are stored as `WorldPredicate` objects in a `WorldOracleStore`. After every
major story event, the event handler writes the new world fact once to the store and
`full_consistency_check(auto_repair=True)` propagates it to all NPCs whose beliefs conflict.
`TemporalBeliefStore` records snapshots at chapter boundaries, enabling writers to query
historical belief states for debugging. NPC dialogue generation receives the current belief
state as context, ensuring the LLM never generates dialogue that contradicts the world model.

## Implementation

```python
from worldoracle import (
    WorldPredicate,
    BeliefState,
    BeliefRepairer,
    ContradictionDetector,
    RepairFrame,
    ConsistencyReport,
    full_consistency_check,
    WorldOracleStore,
    TemporalBeliefStore,
    BeliefSnapshot,
    diff_belief_states,
    BeliefDiff,
    print_beliefs,
    print_repairs,
)
import time

# Shared belief store
store = WorldOracleStore("npc_beliefs.db")
temporal_store = TemporalBeliefStore(store)

# Story event handler: fires when a major world event occurs
def on_story_event(event_type: str, subject: str, new_value, chapter: int):
    """Update the world belief store when a story event fires."""
    predicate = WorldPredicate(
        subject=subject,
        attribute=event_type,
        value=new_value,
        source=f"story_event_ch{chapter}",
        confidence=1.0,
        timestamp=time.time(),
    )

    # Write to all relevant NPCs (or use a global world-state NPC)
    for npc_id in get_npcs_who_know_about(subject):
        state = store.get_belief_state(npc_id)
        state.add(predicate)
        store.save_belief_state(state)

    # Snapshot the belief state at chapter boundaries
    temporal_store.record_snapshot()

# Scene load: run consistency check before dialogue generation
def on_scene_load(area_id: str) -> ConsistencyReport:
    """Run full consistency check and auto-repair on every scene load."""
    report = full_consistency_check(store, auto_repair=True)
    return report

# NPC dialogue context builder: feed current beliefs to LLM
def get_npc_dialogue_context(npc_id: str) -> dict:
    """Build a fact-grounded context dict for LLM dialogue generation."""
    state = store.get_belief_state(npc_id)
    return {
        "npc_id": npc_id,
        "world_facts": {
            f"{p.subject}.{p.attribute}": p.value
            for p in state.predicates
        },
        "confidence": {
            f"{p.subject}.{p.attribute}": p.confidence
            for p in state.predicates
        },
    }

# Writer QA tool: temporal belief debugging
def debug_npc_belief_at_chapter(npc_id: str, subject: str,
                                  attribute: str, chapter: int) -> dict:
    """Answer: 'What did this NPC believe about X at the start of Chapter N?'"""
    chapter_timestamp = get_chapter_start_timestamp(chapter)
    snapshot = temporal_store.get_belief_at(subject, attribute, chapter_timestamp)
    current = store.get_belief_state(npc_id)
    current_pred = next(
        (p for p in current.predicates
         if p.subject == subject and p.attribute == attribute), None
    )

    return {
        "npc_id": npc_id,
        "belief_at_chapter": {
            "chapter": chapter,
            "value": snapshot.value if snapshot else "no belief recorded",
            "confidence": snapshot.confidence if snapshot else None,
            "source": snapshot.source if snapshot else None,
        },
        "current_belief": {
            "value": current_pred.value if current_pred else "no current belief",
            "confidence": current_pred.confidence if current_pred else None,
        },
        "belief_changed": snapshot and current_pred and snapshot.value != current_pred.value,
    }

# Weekly QA diff: what changed in NPC beliefs this sprint?
def sprint_belief_diff(sprint_start_ts: float, sprint_end_ts: float) -> BeliefDiff:
    """Show writers what NPC beliefs changed during the sprint."""
    return diff_belief_states(store, sprint_start_ts, sprint_end_ts)
```

## Results

| Metric | Before | After |
|---|---|---|
| Immersion-breaking NPC contradictions | 34% of QA bug reports | Eliminated (0 in last 2 months) |
| Consistency check runtime | N/A (no check existed) | 12ms (runs on every scene load) |
| QA time to reproduce NPC inconsistency | 45–90 minutes | <5 minutes (temporal query) |
| Story debugging speed | Manual playthrough required | `get_belief_at()` query in seconds |
| Writer QA confidence before scene commit | Low | High (diff shows all belief changes) |
| NPC belief states managed | 300 (fragmented dicts) | 300 (unified WorldOracleStore) |

The 12ms consistency check runtime made it practical to run on every scene load — the player
never perceives it. The previous approach would have required a dedicated QA pass after every
story event to manually check all affected NPCs. With `full_consistency_check(auto_repair=True)`,
contradictions are repaired automatically the moment the scene loads, before any NPC generates
dialogue.

## Key Takeaways

- Running `full_consistency_check(auto_repair=True)` on every scene load (12ms) is the right
  cadence: contradictions are caught at the moment they would become visible to the player, not
  in a separate QA pass.
- `TemporalBeliefStore.get_belief_at()` is a writer productivity tool as much as a debugging
  tool — answering "what did Elara believe in Chapter 3?" is critical for understanding whether
  a dialogue bug is in the event handler or the original writing.
- `BeliefRepairer` with `prefer_higher_confidence` strategy is the right default for story
  games: first-party story events have confidence=1.0 and always win over rumor or
  player-reported beliefs (confidence=0.5).
- `diff_belief_states()` used as a sprint review tool gave writers a structured changelog of
  world model changes, replacing "I think I updated that NPC" with a concrete diff.
- Content-addressing `WorldPredicate` by `SHA-256(subject|attribute|str(value))` means the
  same belief written by two different event handlers is deduplicated automatically — no
  duplicate propagation logic needed.

## Try It Yourself

```bash
pip install worldoracle

# Add NPC beliefs about the world
worldoracle add guard-captain thornwood status active \
    --source quest-giver --confidence 0.8 --timestamp 100
worldoracle add guard-captain thornwood status destroyed \
    --source story-event --confidence 1.0 --timestamp 200

# Detect the contradiction
worldoracle check guard-captain

# Auto-repair: higher confidence wins
worldoracle repair guard-captain

# View current beliefs
worldoracle beliefs guard-captain
```
