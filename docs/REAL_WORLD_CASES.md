# Real-world cases driving worldoracle

## LEGAL-NO-AUTOFIX / G-CONTRA (farm_memory) — CRITICAL

**Source:** Qdrant `farm_memory` Pioneer Content Foundry legal gates rule.

**Rule:** G-CONTRA, G-FOOTAGE-THEME, G-CONTEXT, G-BLACKFREEZE, G-FRAME-LAYOUT are
human-review-only. Automated loops must stop and escalate — never auto-fix legal gates.

**What failed:** Pipelines that defaulted to auto-repair silently “fixed” contested
beliefs and shipped inconsistent worlds.

**Product:**

| Control | API |
|---------|-----|
| Default mode | `gate_beliefs(mode="human_required")` |
| Contradiction | FAIL + `human_required=True` (exit 1) |
| Raise form | `assert_beliefs_clean` → `ClosedLoopError` |
| Opt-in repair | `mode="auto_repair"` only when explicitly requested |

**Tests:** `tests/test_closed_loop_reader.py` — contradiction human_required,
auto_repair opt-in, assert raises.

## Phase-order / G-CONTRA-ORDER (farm) — CRITICAL

**Failure:** `check_contradictions` ran before footage/predicates existed → every
fresh episode blocked with false contradictions.

**Product:**

| Control | API |
|---------|-----|
| Empty store | FAIL_LOUD (exit 2) — refuse check before data |
| Too few predicates | FAIL_LOUD via `min_predicates` phase guard |

**Tests:** empty store FAIL_LOUD; min_predicates FAIL_LOUD.

## Marketing case studies (narrative, not farm evidence)

| Doc | Maps to product |
|-----|-----------------|
| `docs/case-studies/enterprise-multi-source-factbase.md` | Multi-source consistency → `gate_beliefs` |
| `docs/case-studies/gaming-npc-world-consistency.md` | NPC belief contradictions → human_required |
| `docs/case-studies/indie-game-npc-dynamic-dialogue.md` | Dynamic dialogue state → consistency score |

**Non-Ornament:** Import `gate_beliefs` in CI/pipeline; never treat empty world as
PASS; never auto_repair legal gates without an explicit mode flag.
