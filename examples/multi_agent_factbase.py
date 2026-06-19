"""
multi_agent_factbase.py — Enterprise multi-agent knowledge base repair.

5 AI research agents independently gather facts about "TechCorp Inc" from
different data sources (LinkedIn, Crunchbase, news articles, SEC filings,
company website).  Their findings contain contradictions — worldoracle
detects them and repairs the shared knowledge base, flagging cases where
human review is needed (confidence delta < 0.15).

Run:
    python examples/multi_agent_factbase.py
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


BASE_TS = 1_750_400_000.0
HUMAN_REVIEW_CONFIDENCE_DELTA = 0.15   # flag if |conf_a - conf_b| < 0.15

AGENTS = {
    "agent-linkedin": "LinkedIn Scraper",
    "agent-crunchbase": "Crunchbase API",
    "agent-news": "News Article Parser",
    "agent-sec": "SEC EDGAR Filings",
    "agent-website": "Company Website Crawler",
}

COMPANY = "TechCorp_Inc"


def t(offset: float) -> float:
    return BASE_TS + offset


def hr(char: str = "─", width: int = 72) -> None:
    print(char * width)


# ── Fact gathering simulation ─────────────────────────────────────────────────

def gather_agent_facts(store: WorldOracleStore) -> BeliefState:
    """
    Simulate 5 agents gathering 35 facts about TechCorp Inc.
    Contradictions are intentionally present in 6 attributes.
    """
    state = BeliefState(npc_id="techcorp_kb")
    preds: list[WorldPredicate] = []

    # ── ATTRIBUTE: employee_count ─────────────────────────────────────────
    # LinkedIn says 1200 (pulled last week — but may include contractors)
    preds.append(WorldPredicate(
        subject=COMPANY, attribute="employee_count",
        value=1200,
        source="agent-linkedin",
        confidence=0.75,
        timestamp=t(-86400 * 7),    # 7 days ago
    ))
    # Crunchbase says 850 (pulled 3 months ago, excludes contractors)
    preds.append(WorldPredicate(
        subject=COMPANY, attribute="employee_count",
        value=850,
        source="agent-crunchbase",
        confidence=0.70,
        timestamp=t(-86400 * 90),   # 90 days ago
    ))
    # News article from last month cited 1100 (recent layoffs not reflected)
    preds.append(WorldPredicate(
        subject=COMPANY, attribute="employee_count",
        value=1100,
        source="agent-news",
        confidence=0.65,
        timestamp=t(-86400 * 30),   # 30 days ago
    ))

    # ── ATTRIBUTE: ceo ────────────────────────────────────────────────────
    # LinkedIn: current CEO is Sarah Chen (profile updated 1 month ago)
    preds.append(WorldPredicate(
        subject=COMPANY, attribute="ceo",
        value="Sarah_Chen",
        source="agent-linkedin",
        confidence=0.90,
        timestamp=t(-86400 * 30),
    ))
    # Crunchbase: CEO is Marcus Webb (old data — leadership change wasn't updated)
    preds.append(WorldPredicate(
        subject=COMPANY, attribute="ceo",
        value="Marcus_Webb",
        source="agent-crunchbase",
        confidence=0.60,
        timestamp=t(-86400 * 180),  # 6 months old
    ))
    # Company website: Sarah Chen (most authoritative, scraped yesterday)
    preds.append(WorldPredicate(
        subject=COMPANY, attribute="ceo",
        value="Sarah_Chen",
        source="agent-website",
        confidence=0.98,
        timestamp=t(-86400),
    ))

    # ── ATTRIBUTE: funding_status ─────────────────────────────────────────
    # Crunchbase: TechCorp raised Series C ($42M) — still active
    preds.append(WorldPredicate(
        subject=COMPANY, attribute="funding_status",
        value="Series_C_active",
        source="agent-crunchbase",
        confidence=0.80,
        timestamp=t(-86400 * 60),
    ))
    # News: article says TechCorp was acquired by Apex Holdings last month
    preds.append(WorldPredicate(
        subject=COMPANY, attribute="funding_status",
        value="acquired_by_Apex_Holdings",
        source="agent-news",
        confidence=0.72,
        timestamp=t(-86400 * 25),
    ))
    # SEC EDGAR: acquisition filing confirmed (10-K/8-K filed, authoritative)
    preds.append(WorldPredicate(
        subject=COMPANY, attribute="funding_status",
        value="acquired_by_Apex_Holdings",
        source="agent-sec",
        confidence=0.99,
        timestamp=t(-86400 * 20),
    ))

    # ── ATTRIBUTE: annual_revenue_usd ─────────────────────────────────────
    # SEC: $58M ARR from most recent 10-K
    preds.append(WorldPredicate(
        subject=COMPANY, attribute="annual_revenue_usd",
        value=58_000_000,
        source="agent-sec",
        confidence=0.98,
        timestamp=t(-86400 * 100),
    ))
    # News: $72M ARR cited in a press release (includes post-acquisition revenue)
    preds.append(WorldPredicate(
        subject=COMPANY, attribute="annual_revenue_usd",
        value=72_000_000,
        source="agent-news",
        confidence=0.65,
        timestamp=t(-86400 * 15),
    ))

    # ── ATTRIBUTE: office_locations ───────────────────────────────────────
    # Website: HQ in San Francisco, offices in Austin and London
    preds.append(WorldPredicate(
        subject=COMPANY, attribute="office_locations",
        value="SF,Austin,London",
        source="agent-website",
        confidence=0.92,
        timestamp=t(-86400),
    ))
    # LinkedIn: HQ SF, Austin, London, New York (new NY office opened)
    preds.append(WorldPredicate(
        subject=COMPANY, attribute="office_locations",
        value="SF,Austin,London,New_York",
        source="agent-linkedin",
        confidence=0.80,
        timestamp=t(-86400 * 14),
    ))

    # ── ATTRIBUTE: tech_stack_primary (close call — human review needed) ──
    # Crunchbase tech profile: React + Node.js
    preds.append(WorldPredicate(
        subject=COMPANY, attribute="tech_stack_primary",
        value="React_NodeJS",
        source="agent-crunchbase",
        confidence=0.68,
        timestamp=t(-86400 * 45),
    ))
    # News article (job postings analysis): React + Go
    preds.append(WorldPredicate(
        subject=COMPANY, attribute="tech_stack_primary",
        value="React_Go",
        source="agent-news",
        confidence=0.62,
        timestamp=t(-86400 * 10),
    ))

    # ── Consistent facts (no contradictions) ─────────────────────────────
    consistent_facts = [
        WorldPredicate(COMPANY, "founded_year", 2018, "agent-crunchbase", 1.0, t(-86400*60)),
        WorldPredicate(COMPANY, "hq_city", "San_Francisco", "agent-website", 1.0, t(-86400)),
        WorldPredicate(COMPANY, "industry", "SaaS_HR_Tech", "agent-crunchbase", 0.95, t(-86400*60)),
        WorldPredicate(COMPANY, "legal_name", "TechCorp_Inc", "agent-sec", 1.0, t(-86400*20)),
        WorldPredicate(COMPANY, "ticker_symbol", "Not_public", "agent-sec", 1.0, t(-86400*20)),
        WorldPredicate(COMPANY, "product_category", "HR_Software", "agent-website", 0.98, t(-86400)),
        WorldPredicate(COMPANY, "glassdoor_rating", "4.1", "agent-linkedin", 0.85, t(-86400*7)),
        WorldPredicate(COMPANY, "b2b_focus", True, "agent-crunchbase", 0.95, t(-86400*60)),
        WorldPredicate(COMPANY, "has_api", True, "agent-website", 1.0, t(-86400)),
        WorldPredicate(COMPANY, "soc2_compliant", True, "agent-sec", 0.98, t(-86400*20)),
        WorldPredicate(COMPANY, "gdpr_compliant", True, "agent-website", 0.97, t(-86400)),
        WorldPredicate(COMPANY, "open_source_components", True, "agent-news", 0.75, t(-86400*30)),
        WorldPredicate(COMPANY, "series_b_year", 2022, "agent-crunchbase", 1.0, t(-86400*60)),
        WorldPredicate(COMPANY, "lead_investor_series_b", "Horizon_Ventures", "agent-crunchbase", 0.95, t(-86400*60)),
        WorldPredicate(COMPANY, "nps_score", 68, "agent-news", 0.70, t(-86400*45)),
        WorldPredicate(COMPANY, "churn_rate_annual_pct", "8.5", "agent-sec", 0.90, t(-86400*20)),
        WorldPredicate(COMPANY, "enterprise_customers", 320, "agent-website", 0.88, t(-86400)),
        WorldPredicate(COMPANY, "smb_customers", 1400, "agent-linkedin", 0.72, t(-86400*7)),
        WorldPredicate(COMPANY, "patent_count", 14, "agent-sec", 1.0, t(-86400*20)),
        WorldPredicate(COMPANY, "iso27001_certified", True, "agent-sec", 1.0, t(-86400*20)),
        WorldPredicate(COMPANY, "founders_count", 3, "agent-crunchbase", 1.0, t(-86400*60)),
    ]
    preds.extend(consistent_facts)

    for p in preds:
        state.add(p)
        store.save_predicate("techcorp_kb", p)

    return state


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    print()
    hr("═")
    print("  MULTI-AGENT KNOWLEDGE BASE — CONFLICT REPAIR REPORT")
    print(f"  Target:  TechCorp Inc  |  Engine: worldoracle")
    print(f"  Agents:  {len(AGENTS)}  |  Date: {time.strftime('%Y-%m-%d %H:%M UTC')}")
    hr("═")

    store = WorldOracleStore(":memory:")
    detector = ContradictionDetector()
    repairer = BeliefRepairer()

    print("\n[1/3] Collecting agent research findings …")
    state = gather_agent_facts(store)
    total_facts = len(state.predicates)
    print(f"      Agents deployed:     {len(AGENTS)}")
    for agent_id, label in AGENTS.items():
        count = sum(1 for p in state.predicates if p.source == agent_id)
        print(f"        • {label:<35} {count} facts")
    print(f"      Total facts:         {total_facts}")

    print("\n[2/3] Detecting contradictions …")
    contradictions = detector.detect(state)
    print(f"      Contradictions:      {len(contradictions)}")

    print("\n[3/3] Repairing knowledge base …")
    auto_repaired: list[tuple] = []
    human_review: list[tuple] = []

    for pred_a, pred_b in contradictions:
        frame = repairer.repair(pred_a, pred_b)
        store.save_repair(frame)
        delta = abs(pred_a.confidence - pred_b.confidence)
        if delta < HUMAN_REVIEW_CONFIDENCE_DELTA:
            human_review.append((pred_a, pred_b, frame))
        else:
            auto_repaired.append((pred_a, pred_b, frame))

    print(f"      Auto-repaired:       {len(auto_repaired)} (clear winner)")
    print(f"      Human review needed: {len(human_review)} "
          f"(confidence delta < {HUMAN_REVIEW_CONFIDENCE_DELTA})")

    consistent_facts = total_facts - len(contradictions) * 2  # rough estimate
    consistent_final = total_facts - len(contradictions)

    hr()
    print()
    print(f"  KNOWLEDGE BASE REPAIR: {total_facts} facts gathered by {len(AGENTS)} agents, "
          f"{len(contradictions)} contradictions detected. "
          f"{len(auto_repaired)} auto-repaired (clear winner), "
          f"{len(human_review)} flagged for human review "
          f"(confidence delta <{HUMAN_REVIEW_CONFIDENCE_DELTA}). "
          f"Final KB: {total_facts - len(contradictions)} consistent facts.")
    hr()

    # Detailed repair output
    print("\n  AUTO-REPAIRED CONTRADICTIONS:")
    print()
    for pred_a, pred_b, frame in auto_repaired:
        winner = pred_a if frame.resolved_value == pred_a.value else pred_b
        loser = pred_b if frame.resolved_value == pred_a.value else pred_a
        print(f"  Attribute:  {pred_a.subject}.{pred_a.attribute}")
        print(f"  Conflict:   [{pred_a.source}] → {pred_a.value!r}  "
              f"(conf={pred_a.confidence:.2f}, "
              f"age={int((BASE_TS - pred_a.timestamp)/86400)}d)")
        print(f"              [{pred_b.source}] → {pred_b.value!r}  "
              f"(conf={pred_b.confidence:.2f}, "
              f"age={int((BASE_TS - pred_b.timestamp)/86400)}d)")
        print(f"  Resolved:   {frame.resolved_value!r}  "
              f"← {winner.source}  [{frame.strategy}]")
        print(f"  Reason:     {frame.reason}")
        print(f"  Discarded:  {loser.source}'s value overridden.")
        print()

    hr()
    print("\n  FLAGGED FOR HUMAN REVIEW (confidence too close to call):")
    print()
    for pred_a, pred_b, frame in human_review:
        delta = abs(pred_a.confidence - pred_b.confidence)
        print(f"  Attribute:  {pred_a.subject}.{pred_a.attribute}")
        print(f"  Option A:   [{pred_a.source}] → {pred_a.value!r}  "
              f"(conf={pred_a.confidence:.2f})")
        print(f"  Option B:   [{pred_b.source}] → {pred_b.value!r}  "
              f"(conf={pred_b.confidence:.2f})")
        print(f"  Δ conf:     {delta:.2f}  (threshold: {HUMAN_REVIEW_CONFIDENCE_DELTA})")
        print(f"  Suggestion: {frame.resolved_value!r}  (system would pick this, but defer to human)")
        print(f"  Action:     → FLAG FOR ANALYST REVIEW before publishing to report.")
        print()

    hr()
    print()
    print(f"  FINAL KNOWLEDGE BASE SUMMARY — TechCorp Inc:")
    print()

    # Build canonical facts (use repaired values)
    resolved_values: dict[str, object] = {}
    for p in state.predicates:
        key = f"{p.subject}.{p.attribute}"
        if key not in resolved_values:
            resolved_values[key] = p.value
    for pred_a, pred_b, frame in (auto_repaired + human_review):
        key = f"{pred_a.subject}.{pred_a.attribute}"
        resolved_values[key] = frame.resolved_value

    for key, val in sorted(resolved_values.items()):
        attr = key.split(".", 1)[1]
        flag = " [REVIEW]" if any(
            f"{a.subject}.{a.attribute}" == key
            for a, b, _ in human_review
        ) else ""
        print(f"    {attr:<40} {val!r}{flag}")

    print()
    hr("═")
    print(f"\n  Report complete. {len(auto_repaired)} facts auto-repaired, "
          f"{len(human_review)} sent to human analyst queue.")
    print()


if __name__ == "__main__":
    main()
