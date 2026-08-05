# Real-world cases driving worldoracle

## LEGAL-NO-AUTOFIX / G-CONTRA (farm_memory)

**Rule:** G-CONTRA, G-FOOTAGE-THEME, G-CONTEXT, G-BLACKFREEZE, G-FRAME-LAYOUT are
human-review-only. Automated loops must stop and escalate — never auto-fix legal gates.

**Product:** `gate_beliefs(mode="human_required")` default — contradictions → FAIL + human_required.

## Phase-order bug

**Failure:** check_contradictions ran before footage existed → every fresh episode blocked.

**Product:** empty store / too few predicates → FAIL_LOUD (refuse check before data exists).
