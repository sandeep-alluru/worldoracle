# Architecture

## Overview

worldoracle is structured as a layered library with a clean separation between
the core data model, persistence, CLI, and server interfaces.

## Layers

```
┌─────────────────────────────────────────────────────┐
│  CLI (cli.py)    FastAPI (api.py)   MCP (mcp_server.py) │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│                  Formatters (report.py)              │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│             Persistence (store.py / SQLite)          │
└──────────────────────┬──────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────┐
│    Core Model (predicate.py)                         │
│    WorldPredicate · BeliefState                      │
│    ContradictionDetector · BeliefRepairer            │
│    RepairFrame                                       │
└─────────────────────────────────────────────────────┘
```

## Core Data Model (`predicate.py`)

### WorldPredicate

A typed, content-addressed belief: `subject` has `attribute = value`.

- **Content addressing**: ID is SHA-256[:16] of `subject|attribute|str(value)`.
  Identical facts always produce the same ID, making deduplication trivial.
- **Metadata**: `source`, `confidence`, `timestamp` drive repair strategy selection.

### BeliefState

An NPC's complete world model — a list of WorldPredicates, also content-addressed
from its predicate IDs.

### ContradictionDetector

Groups predicates by `(subject, attribute)` and reports pairs where `value` differs.
O(n²) within each group but groups are small in practice.

### BeliefRepairer

Resolves a contradiction pair using a priority chain:

1. **prefer_newer** — higher `timestamp` wins
2. **prefer_higher_confidence** — higher `confidence` wins
3. **prefer_observation** — `source == "observation"` wins
4. **default** — keep `pred_a`

Each resolution produces a `RepairFrame` (also content-addressed).

## Persistence (`store.py`)

SQLite with two tables:

- `predicates(id, npc_id, subject, attribute, value, source, confidence, timestamp)`
- `repairs(id, predicate_a_id, predicate_b_id, strategy, resolved_value, reason, timestamp)`

Values are JSON-encoded to handle arbitrary Python types (bool, int, str, float, list).

## Design Decisions

- **Flat value encoding** (JSON): avoids a separate `value_type` column; supports
  future complex values (lists, dicts) without schema migration.
- **Content addressing throughout**: makes the system idempotent — inserting the
  same predicate twice is a no-op at the DB level (INSERT OR REPLACE).
- **In-memory default**: `WorldOracleStore(":memory:")` requires no setup,
  ideal for testing and ephemeral game sessions.
- **No external deps in core**: `predicate.py` and `store.py` only use stdlib.
  `rich` and `click` are presentation-layer deps.
