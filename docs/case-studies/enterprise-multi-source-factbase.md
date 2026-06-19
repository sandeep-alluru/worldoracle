# Case Study: Automated Contradiction Resolution Across 50+ Data Sources

## Company Profile

**Meridian Intelligence** is a market research firm with 30 engineers that aggregates
competitive intelligence for enterprise clients. Their AI platform synthesizes data from 50+
sources — news APIs, LinkedIn, Crunchbase, SEC EDGAR, financial data providers, Twitter/X, and
industry analyst reports — to produce weekly market intelligence briefings. Their stack is
Python, FastAPI, PostgreSQL, ClickHouse (event warehouse), and an LLM API for narrative
synthesis. They serve 15 enterprise clients with annual contracts averaging $180,000.

## The Problem

Meridian's platform collected data from 50+ sources that frequently contradicted each other.
For any given company under research, the platform might simultaneously hold:

- Employee count: 2,400 (LinkedIn) vs 1,680 (Crunchbase) vs 2,100 (company website)
- CEO: "Sarah Chen" (company website, 6 months old) vs "Marcus Webb" (LinkedIn, 3 weeks old,
  reflecting a leadership change)
- Funding status: "Series B, $45M" (Crunchbase) vs "Series C, $67M" (TechCrunch article from
  last week) vs "Series B, $45M" (AngelList, outdated)
- Revenue: "$120M ARR" (investor memo, Q3) vs "$140M ARR" (earnings call transcript, Q4)

An analyst spent 4 hours per report manually reconciling these contradictions — checking source
dates, assessing credibility, and choosing which value to use. For 15 clients each receiving
weekly reports, this was 60 analyst-hours per week of pure contradiction-resolution work.

The contradiction rate was also increasing. As Meridian added more data sources, each new
source added to the contradiction surface area. Their estimate was that every new source added
approximately 0.3 additional contradictions per company per report cycle.

A second problem was report reviews: analysts spent 45 minutes re-reading each report to find
what had changed since last week. A company that went through a funding round, a CEO change, and
two product announcements in one week required a careful diff of the full current report against
the previous week's — a slow, error-prone process.

## Solution Architecture

```
50+ Data Sources (ingestion pipeline)
--------------------------------------
news_api → WorldPredicate(subject="ACME", attribute="ceo", value="Marcus Webb",
                           source="linkedin", confidence=0.9, timestamp=T_new)
crunchbase → WorldPredicate(subject="ACME", attribute="ceo", value="Sarah Chen",
                              source="crunchbase", confidence=0.7, timestamp=T_old)
           │
     WorldOracleStore.save_predicate()  (both written — no discard at ingest)
           │
BeliefState("ACME") → now contains contradiction on ceo attribute
           │
ContradictionDetector.detect(state)
  → [(predicate_linkedin, predicate_crunchbase)]
           │
BeliefRepairer.repair(p_a, p_b, strategy="prefer_newer")
  → RepairFrame(resolved_value="Marcus Webb", strategy="prefer_newer",
                winner=p_linkedin, loser=p_crunchbase)
           │
TemporalBeliefStore.record_snapshot()  → snapshot for diff next week
           │
diff_belief_states(store, last_week_ts, this_week_ts)
  → BeliefDiff(added=3, removed=1, modified=4, stable=89)
  → analyst reviews 8 changes instead of 97 facts
```

Every data point ingested is stored as a `WorldPredicate` with source and confidence. The store
holds all versions — the contradiction is a first-class object, not a pre-ingestion discard.
`ContradictionDetector` finds all conflicts across sources. `BeliefRepairer` resolves them using
configurable strategies: `prefer_newer` for leadership and product facts, `prefer_higher_confidence`
for financial figures where Meridian's data quality scores differ by source. `TemporalBeliefStore`
snapshots the resolved state weekly, enabling `diff_belief_states()` to produce a structured
changelog for analyst review.

## Implementation

```python
from worldoracle import (
    WorldPredicate,
    BeliefState,
    ContradictionDetector,
    BeliefRepairer,
    RepairFrame,
    ConsistencyReport,
    full_consistency_check,
    WorldOracleStore,
    TemporalBeliefStore,
    BeliefSnapshot,
    BeliefDiff,
    diff_belief_states,
    print_repairs,
    to_json,
)
import time

store = WorldOracleStore("market_intel.db")
temporal_store = TemporalBeliefStore(store)

# Source confidence scores — calibrated against ground truth audits
SOURCE_CONFIDENCE = {
    "sec_edgar": 0.99,      # Regulatory filings — highest confidence
    "linkedin": 0.85,       # Fresh but self-reported
    "crunchbase": 0.72,     # Often 3–6 months stale
    "news_api": 0.80,       # Timely but may be rumors
    "company_website": 0.78,  # Authoritative but often outdated
    "twitter": 0.55,        # Fast but unverified
    "angellist": 0.65,      # Often stale
}

def ingest_data_point(company_ticker: str, attribute: str,
                       value, source: str, timestamp: float):
    """Ingest a single data point — store the predicate, resolve contradictions later."""
    confidence = SOURCE_CONFIDENCE.get(source, 0.60)

    predicate = WorldPredicate(
        subject=company_ticker,
        attribute=attribute,
        value=value,
        source=source,
        confidence=confidence,
        timestamp=timestamp,
    )

    state = store.get_belief_state(company_ticker)
    state.add(predicate)
    store.save_belief_state(state)

def resolve_all_contradictions() -> ConsistencyReport:
    """Run full contradiction resolution across all companies in the store.

    Called nightly after the full ingestion pipeline completes.
    """
    report = full_consistency_check(store, auto_repair=True)
    # Snapshot after repair for weekly diff
    temporal_store.record_snapshot()
    return report

def build_company_profile(ticker: str) -> dict:
    """Build a clean, contradiction-free company profile for report generation."""
    state = store.get_belief_state(ticker)
    detector = ContradictionDetector()
    contradictions = detector.detect(state)

    if contradictions:
        # Any remaining contradictions after nightly repair — surface for analyst
        unresolved = []
        for pred_a, pred_b in contradictions:
            unresolved.append({
                "attribute": pred_a.attribute,
                "source_a": {"source": pred_a.source, "value": pred_a.value,
                              "confidence": pred_a.confidence},
                "source_b": {"source": pred_b.source, "value": pred_b.value,
                              "confidence": pred_b.confidence},
            })
    else:
        unresolved = []

    return {
        "ticker": ticker,
        "facts": {
            f"{p.subject}.{p.attribute}": {
                "value": p.value,
                "source": p.source,
                "confidence": p.confidence,
                "timestamp": p.timestamp,
            }
            for p in state.predicates
        },
        "unresolved_contradictions": unresolved,
        "ready_for_report": len(unresolved) == 0,
    }

def weekly_diff_report(ticker: str, last_week_ts: float,
                        this_week_ts: float) -> dict:
    """Show analyst exactly what changed since last week — no full re-read required."""
    diff: BeliefDiff = diff_belief_states(
        store,
        before_timestamp=last_week_ts,
        after_timestamp=this_week_ts,
        subject=ticker,
    )

    # Categorize changes for analyst review
    leadership_changes = [
        c for c in diff.changes
        if c.predicate in ("ceo", "cto", "cfo", "founder")
    ]
    financial_changes = [
        c for c in diff.changes
        if c.predicate in ("revenue", "funding", "valuation", "arr")
    ]
    operational_changes = [
        c for c in diff.changes
        if c.predicate in ("employee_count", "headcount", "office_count")
    ]

    return {
        "ticker": ticker,
        "summary": diff.summary,
        "total_changes": len(diff.changes),
        "leadership_changes": leadership_changes,
        "financial_changes": financial_changes,
        "operational_changes": operational_changes,
        "stable_facts": diff.stable,
        "review_required": len(diff.changes) > 0,
    }
```

## Results

| Metric | Before | After |
|---|---|---|
| Manual contradiction reconciliation | 4 hours per report | 0 hours (fully automated) |
| Weekly contradiction reports per analyst | 60 hours | <5 minutes (diff review only) |
| Analyst time to review weekly changes | 45 min (full re-read) | <10 minutes (diff_belief_states) |
| Data sources unified | 50+ (fragmented) | 50+ (single WorldOracleStore) |
| Contradictions surfaced and logged | 0 (invisible) | All (auditable) |
| Unresolved contradictions requiring review | Unknown | Surfaced in profile (flagged) |
| Enterprise clients served | 15 | 15 (with SLA on contradiction resolution) |
| New source integration overhead | 2 engineer-days | 1 hour (add to SOURCE_CONFIDENCE) |

The most transformative improvement was `diff_belief_states()` replacing the weekly full re-read.
Analysts review 8–15 changes per company per week rather than scanning 97 facts looking for
what's new. For a company that had a quiet week (stable facts), the diff shows 0 changes and
the analyst spends 30 seconds confirming and moving on. For a company that went through a
funding round, the diff surfaces the 4 changed facts immediately.

## Key Takeaways

- `WorldPredicate` with `source` and `confidence` fields is the architecture that makes
  contradiction resolution principled: the `BeliefRepairer` doesn't guess — it applies a
  declared strategy (prefer_newer, prefer_higher_confidence) to source-attributed facts.
- Storing all predicates (including contradicting ones) at ingest time, rather than discarding
  the "loser" immediately, preserves the audit trail and allows strategy changes to be
  back-applied.
- `diff_belief_states()` is the analyst-facing product — it replaced a 45-minute weekly
  re-read with a <10-minute structured review, which is where most of the measurable time
  savings came from.
- `full_consistency_check(auto_repair=True)` nightly, combined with `record_snapshot()`,
  creates the temporal chain that makes `diff_belief_states()` possible — the two calls must
  both be present.
- Calibrating `SOURCE_CONFIDENCE` scores against ground truth audits (cross-referencing SEC
  filings as ground truth for financial figures) is the work that makes the automated repair
  trustworthy. This calibration took 2 days and is the most important configuration step.

## Try It Yourself

```bash
pip install worldoracle

# Simulate two conflicting data sources
worldoracle add ACME ceo "Sarah Chen" --source crunchbase --confidence 0.72 --timestamp 100
worldoracle add ACME ceo "Marcus Webb" --source linkedin --confidence 0.85 --timestamp 200

# Detect the contradiction
worldoracle check ACME

# Repair: newer + higher confidence wins
worldoracle repair ACME

# View resolved belief state
worldoracle beliefs ACME
```
