"""
live_game_event_tracker.py — Live sports match state maintained by worldoracle.

A simulated football match (Team A vs Team B) is tracked in real time by
3 analyst agents: TV_Feed, Radio_Commentary, and Official_Stats.  Each agent
independently reports match events, but their reports can contradict:

  • After the 22nd-minute goal by Reyes_J, Radio_Commentary (which had a
    30-second feed delay) still reports the score as 1-1 while TV_Feed and
    Official_Stats correctly report 2-1.
  • TV_Feed reports the wrong player name for a substitution (typo in their
    lineup sheet: "Ivanova_M" instead of the correct "Ivanova_N").

worldoracle detects both contradictions in real time, repairs them using
the most authoritative source (Official_Stats: confidence 1.00), and
prints the verified half-time world state.

Run:
    python examples/live_game_event_tracker.py
"""
from __future__ import annotations

import time
from collections import defaultdict

from worldoracle.predicate import (
    BeliefRepairer,
    BeliefState,
    ContradictionDetector,
    RepairFrame,
    WorldPredicate,
)
from worldoracle.store import WorldOracleStore


BASE_TS = 1_750_500_000.0     # kick-off epoch

TEAM_A = "Team_A_FC"
TEAM_B = "Team_B_United"
MATCH_ID = "MATCH-2026-FA-CUP-SEMI-001"

# Analyst agents (sources)
TV_FEED = "TV_Feed"
RADIO = "Radio_Commentary"
OFFICIAL = "Official_Stats"

# Source confidence weights
SOURCE_CONFIDENCE = {
    OFFICIAL: 1.00,
    TV_FEED: 0.88,
    RADIO: 0.72,
}


def t(offset_seconds: float) -> float:
    return BASE_TS + offset_seconds


def match_clock(offset_seconds: float) -> str:
    m, s = divmod(int(offset_seconds), 60)
    return f"{m}'{s:02d}\""


def hr(char: str = "─", width: int = 72) -> None:
    print(char * width)


# ── First half event log ──────────────────────────────────────────────────────
#
# We model events as a flat list of WorldPredicates.  For each scoreline
# change, we record one predicate per source — using a unique attribute name
# per event so only the deliberate contradiction (radio lag on the 22' goal)
# shows up.
#
# Predicates are keyed by (subject, attribute).  When two sources report
# different values for the SAME (subject, attribute) key, worldoracle flags it.

def build_first_half_predicates() -> list[WorldPredicate]:
    """
    Build 35 predicates covering the first half of the match.

    Deliberate contradictions:
      [1] score_at_22min — Radio says '1-1', Official + TV say '2-1'
      [2] sub_team_b_25min — TV says 'Ivanova_M', Official + Radio say 'Ivanova_N'
    """
    preds: list[WorldPredicate] = []

    # ── Kick-off ────────────────────────────────────────────────────────────
    preds.append(WorldPredicate(
        subject="Match", attribute="status",
        value="in_play",
        source=OFFICIAL, confidence=1.00, timestamp=t(0),
    ))

    # ── Foul @ 3' ───────────────────────────────────────────────────────────
    preds.append(WorldPredicate(
        subject="Foul_3min", attribute="committed_by",
        value="Davids_R",
        source=OFFICIAL, confidence=1.00, timestamp=t(180),
    ))
    preds.append(WorldPredicate(
        subject="Foul_3min", attribute="committed_by",
        value="Davids_R",
        source=TV_FEED, confidence=0.88, timestamp=t(182),
    ))

    # ── GOAL @ 7' — Torres_M — score 1-0 ────────────────────────────────────
    preds.append(WorldPredicate(
        subject="Goal_7min", attribute="scorer",
        value="Torres_M",
        source=OFFICIAL, confidence=1.00, timestamp=t(420),
    ))
    preds.append(WorldPredicate(
        subject="Goal_7min", attribute="scorer",
        value="Torres_M",
        source=TV_FEED, confidence=0.92, timestamp=t(425),
    ))
    preds.append(WorldPredicate(
        subject="Goal_7min", attribute="scorer",
        value="Torres_M",
        source=RADIO, confidence=0.78, timestamp=t(450),  # 30s delay
    ))
    # Score consensus after 7' goal — all agree
    preds.append(WorldPredicate(
        subject="Score_after_7min", attribute="value",
        value="1-0",
        source=OFFICIAL, confidence=1.00, timestamp=t(420),
    ))
    preds.append(WorldPredicate(
        subject="Score_after_7min", attribute="value",
        value="1-0",
        source=TV_FEED, confidence=0.88, timestamp=t(425),
    ))
    preds.append(WorldPredicate(
        subject="Score_after_7min", attribute="value",
        value="1-0",
        source=RADIO, confidence=0.72, timestamp=t(450),
    ))

    # ── Yellow card @ 9' — Johansson_K ──────────────────────────────────────
    preds.append(WorldPredicate(
        subject="Johansson_K", attribute="yellow_cards",
        value=1,
        source=OFFICIAL, confidence=1.00, timestamp=t(540),
    ))

    # ── GOAL @ 15' — Müller_A (penalty) — score 1-1 ─────────────────────────
    preds.append(WorldPredicate(
        subject="Goal_15min", attribute="scorer",
        value="Müller_A",
        source=OFFICIAL, confidence=1.00, timestamp=t(900),
    ))
    preds.append(WorldPredicate(
        subject="Goal_15min", attribute="scorer",
        value="Müller_A",
        source=TV_FEED, confidence=0.88, timestamp=t(904),
    ))
    preds.append(WorldPredicate(
        subject="Goal_15min", attribute="scorer",
        value="Müller_A",
        source=RADIO, confidence=0.72, timestamp=t(930),
    ))
    preds.append(WorldPredicate(
        subject="Score_after_15min", attribute="value",
        value="1-1",
        source=OFFICIAL, confidence=1.00, timestamp=t(900),
    ))
    preds.append(WorldPredicate(
        subject="Score_after_15min", attribute="value",
        value="1-1",
        source=TV_FEED, confidence=0.88, timestamp=t(904),
    ))
    preds.append(WorldPredicate(
        subject="Score_after_15min", attribute="value",
        value="1-1",
        source=RADIO, confidence=0.72, timestamp=t(930),
    ))

    # ── Sub @ 18' — Garcia_L on for Nwosu_O ─────────────────────────────────
    preds.append(WorldPredicate(
        subject="Sub_TeamA_18min", attribute="player_on",
        value="Garcia_L",
        source=OFFICIAL, confidence=1.00, timestamp=t(1080),
    ))
    preds.append(WorldPredicate(
        subject="Sub_TeamA_18min", attribute="player_on",
        value="Garcia_L",
        source=TV_FEED, confidence=0.88, timestamp=t(1085),
    ))

    # ── GOAL @ 22' — Reyes_J — score 2-1  [DELIBERATE CONTRADICTION HERE] ──
    preds.append(WorldPredicate(
        subject="Goal_22min", attribute="scorer",
        value="Reyes_J",
        source=OFFICIAL, confidence=1.00, timestamp=t(1320),
    ))
    preds.append(WorldPredicate(
        subject="Goal_22min", attribute="scorer",
        value="Reyes_J",
        source=TV_FEED, confidence=0.88, timestamp=t(1325),
    ))
    preds.append(WorldPredicate(
        subject="Goal_22min", attribute="scorer",
        value="Reyes_J",
        source=RADIO, confidence=0.68, timestamp=t(1350),  # late but still gets it
    ))

    # SCORE AFTER 22': Official + TV correctly report 2-1 at t+1320/1325.
    # Radio is running a 30-second delayed feed.  Their last score update was
    # at t+1290 (before the goal), so their belief timestamp is t+1290 — stale.
    # Official and TV have the newer (t+1320) authoritative data.
    preds.append(WorldPredicate(
        subject="Score_after_22min", attribute="value",
        value="2-1",                       # CORRECT
        source=OFFICIAL, confidence=1.00, timestamp=t(1320),
    ))
    preds.append(WorldPredicate(
        subject="Score_after_22min", attribute="value",
        value="2-1",                       # CORRECT
        source=TV_FEED, confidence=0.88, timestamp=t(1325),
    ))
    # CONTRADICTION: Radio's last update was 30 seconds BEFORE the goal.
    # Timestamp t(1290): that is when Radio's feed last told it the score was 1-1.
    preds.append(WorldPredicate(
        subject="Score_after_22min", attribute="value",
        value="1-1",                       # WRONG — stale, 30s behind
        source=RADIO, confidence=0.72, timestamp=t(1290),
    ))

    # ── Sub @ 25' — Ivanova_N on for Johansson_K  [DELIBERATE CONTRADICTION] ─
    preds.append(WorldPredicate(
        subject="Sub_TeamB_25min", attribute="player_on",
        value="Ivanova_N",                 # CORRECT — official ref's book
        source=OFFICIAL, confidence=1.00, timestamp=t(1502),
    ))
    # TV_Feed had a typo in their pre-match lineup sheet (prepared before kickoff).
    # Their lineup belief timestamp is t(0) — much older — and has wrong name.
    preds.append(WorldPredicate(
        subject="Sub_TeamB_25min", attribute="player_on",
        value="Ivanova_M",                 # WRONG — typo (M vs N) from pre-match sheet
        source=TV_FEED, confidence=0.75, timestamp=t(0),
    ))
    # Radio got it right from the stadium PA announcement
    preds.append(WorldPredicate(
        subject="Sub_TeamB_25min", attribute="player_on",
        value="Ivanova_N",                 # CORRECT
        source=RADIO, confidence=0.70, timestamp=t(1505),
    ))

    # ── Yellow card @ 26' — Park_S ──────────────────────────────────────────
    preds.append(WorldPredicate(
        subject="Park_S", attribute="yellow_cards",
        value=1,
        source=OFFICIAL, confidence=1.00, timestamp=t(1560),
    ))

    # ── Sub @ 28' — Osei_K replaces Torres_M ────────────────────────────────
    preds.append(WorldPredicate(
        subject="Sub_TeamA_28min", attribute="player_on",
        value="Osei_K",
        source=OFFICIAL, confidence=1.00, timestamp=t(1680),
    ))

    # ── Half-time @ 30' ─────────────────────────────────────────────────────
    preds.append(WorldPredicate(
        subject="Match", attribute="status",
        value="halftime",
        source=OFFICIAL, confidence=1.00, timestamp=t(1800),
    ))

    return preds


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print()
    hr("═")
    print(f"  LIVE MATCH TRACKER — {TEAM_A.replace('_FC','')} vs "
          f"{TEAM_B.replace('_United','')}")
    print(f"  Match ID: {MATCH_ID}")
    print(f"  Sources:  {TV_FEED}, {RADIO}, {OFFICIAL}")
    print(f"  Engine:   worldoracle  |  Mode: Real-time belief repair")
    hr("═")

    store = WorldOracleStore(":memory:")
    state = BeliefState(npc_id="live_match")
    detector = ContradictionDetector()
    repairer = BeliefRepairer()

    print("\n[1/3] Processing first-half events …")
    preds = build_first_half_predicates()
    print(f"      Predicates ingested from 3 sources: {len(preds)}")

    # Add all predicates to state
    for p in preds:
        state.add(p)
        store.save_predicate("live_match", p)

    print("\n[2/3] Running contradiction detection …")
    contradictions = detector.detect(state)
    print(f"      Contradictions found: {len(contradictions)}")

    # Real-time style — show each contradiction as it's found
    print()
    repairs: list[RepairFrame] = []
    for pred_a, pred_b in contradictions:
        frame = repairer.repair(pred_a, pred_b)
        store.save_repair(frame)
        repairs.append(frame)
        winner = pred_a if frame.resolved_value == pred_a.value else pred_b
        loser = pred_b if frame.resolved_value == pred_a.value else pred_a
        # Determine approx match clock from the newer predicate's timestamp
        offset = max(pred_a.timestamp, pred_b.timestamp) - BASE_TS
        print(f"  [{match_clock(offset)}] CONTRADICTION: "
              f"{pred_a.subject}.{pred_a.attribute}")
        print(f"           {pred_a.source} says {pred_a.value!r} "
              f"(conf={pred_a.confidence:.2f})")
        print(f"           {pred_b.source} says {pred_b.value!r} "
              f"(conf={pred_b.confidence:.2f})")
        print(f"           RESOLVED → {frame.resolved_value!r} "
              f"[{frame.strategy}] via {winner.source}")
        print()

    print(f"\n[3/3] Generating verified half-time state …")
    hr()

    # Verified score: most recent Official_Stats score predicate
    score_preds_official = sorted(
        [p for p in state.predicates
         if "Score_after" in p.subject and p.source == OFFICIAL],
        key=lambda p: p.timestamp,
        reverse=True,
    )
    verified_score = score_preds_official[0].value if score_preds_official else "unknown"

    # Sub count
    sub_preds = [p for p in state.predicates
                 if "Sub_" in p.subject and p.source == OFFICIAL and p.attribute == "player_on"]
    confirmed_subs = len(sub_preds)
    disputed_subs = len([
        (a, b) for a, b in contradictions
        if "Sub_" in a.subject and a.attribute == "player_on"
    ])

    print()
    print(f"  VERIFIED HALF-TIME STATE:")
    print(f"  {TEAM_A.replace('_FC', '')} {verified_score} "
          f"{TEAM_B.replace('_United', '')}")
    print(f"  Contradictions auto-resolved:  {len(contradictions)} "
          f"(Official_Stats source authoritative)")
    print(f"  Player substitutions:          {confirmed_subs} confirmed, "
          f"{disputed_subs} disputed")
    hr()

    # Key contradiction detail
    print()
    print("  KEY CONTRADICTION #1 — Score at 22' (Radio feed delay):")
    score_contras = [(a, b) for a, b in contradictions
                     if a.subject == "Score_after_22min"]
    if score_contras:
        a, b = score_contras[0]
        frame = next(f for f in repairs
                     if f.predicate_a_id == a.id or f.predicate_b_id == a.id)
        winner = a if frame.resolved_value == a.value else b
        loser = b if frame.resolved_value == a.value else a
        print(f"  {a.source} says {a.value!r}  (conf={a.confidence:.2f}, "
              f"t+{int(a.timestamp-BASE_TS)}s)")
        print(f"  {b.source} says {b.value!r}  (conf={b.confidence:.2f}, "
              f"t+{int(b.timestamp-BASE_TS)}s)")
        print(f"  RESOLVED → {frame.resolved_value!r}  [{frame.strategy}]")
        print(f"  Reason: {frame.reason}")
        print(f"  Root cause: {loser.source} had a 30-second feed delay — "
              f"its last score update (t+1290s) predates the goal (t+1320s). "
              f"Overridden by {winner.source} (newer timestamp).")
    print()

    print("  KEY CONTRADICTION #2 — Substitution player name (TV typo):")
    sub_contras = [(a, b) for a, b in contradictions
                   if a.subject == "Sub_TeamB_25min" and a.attribute == "player_on"]
    if sub_contras:
        a, b = sub_contras[0]
        frame = next(f for f in repairs
                     if f.predicate_a_id == a.id or f.predicate_b_id == a.id)
        winner = a if frame.resolved_value == a.value else b
        loser = b if frame.resolved_value == a.value else a
        print(f"  {a.source} says {a.value!r}  (conf={a.confidence:.2f})")
        print(f"  {b.source} says {b.value!r}  (conf={b.confidence:.2f})")
        print(f"  RESOLVED → {frame.resolved_value!r}  [{frame.strategy}]")
        print(f"  Reason: {frame.reason}")
        print(f"  Root cause: {loser.source} had a typo in their pre-match "
              f"lineup sheet ('Ivanova_M' vs correct 'Ivanova_N'). "
              f"Their belief was formed at t+0 (pre-match). "
              f"Overridden by {winner.source} "
              f"({frame.strategy} — newer timestamp).")

    print()
    hr("═")
    print()
    print(f"  VERIFIED HALF-TIME STATE: "
          f"{TEAM_A.replace('_FC','')} {verified_score} "
          f"{TEAM_B.replace('_United','')} "
          f"({len(contradictions)} contradiction(s) auto-resolved, "
          f"Official_Stats source authoritative). "
          f"Player substitutions: {confirmed_subs} confirmed, "
          f"{disputed_subs} disputed.")
    print()
    print(f"  Report generated at {time.strftime('%Y-%m-%d %H:%M UTC')}")
    hr("═")


if __name__ == "__main__":
    main()
