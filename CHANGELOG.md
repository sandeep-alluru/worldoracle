# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- `TemporalBeliefStore` — snapshot-based belief history with time-travel queries
- `BeliefSnapshot` dataclass for point-in-time belief records
- `belief_drift()` — measure confidence volatility over time (0=stable, 1=volatile)
- `diff_belief_states()` — compare belief states at two timestamps, classifying each change
- `BeliefChange` and `BeliefDiff` dataclasses with added/removed/modified/stable counts
- `full_consistency_check()` — cross-NPC contradiction scan with optional auto-repair
- `ConsistencyReport` with consistency_score, by_subject breakdown, most_contested subjects
- CLI: `worldoracle consistency --repair` and `worldoracle diff --before T1 --after T2` commands

## [0.1.0] - 2026-06-18

### Added
- `WorldPredicate` — content-addressed belief predicate (SHA-256[:16] ID)
- `BeliefState` — NPC world model with content-addressed state ID
- `ContradictionDetector` — detects conflicts in a BeliefState
- `BeliefRepairer` — resolves contradictions with 3 strategies: prefer_newer, prefer_higher_confidence, prefer_observation
- `RepairFrame` — content-addressed repair record
- `WorldOracleStore` — SQLite persistence for predicates and repair frames
- CLI with 5 subcommands: `add`, `check`, `repair`, `beliefs`, `status`
- FastAPI REST server with 5 endpoints
- MCP server with 3 tools for Claude Desktop integration
- OpenAI function-calling tool definitions (`tools/openai-tools.json`)
- Rich table formatters, JSON output, and Markdown report generator
- 67 unit and integration tests, 98%+ coverage

[Unreleased]: https://github.com/sandeep-alluru/worldoracle/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/sandeep-alluru/worldoracle/releases/tag/v0.1.0
