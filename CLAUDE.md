# worldoracle — Session Anchor

**Research spec:** `../tech-research/14-Gaming/causal-world-state-oracle-real-time-contradiction-detect/README.md`  
**One-liner:** Real-time contradiction detector for NPC world state — split soft narrative from hard predicates  
**Phase:** backlog  
**Stack:** Python, sqlite3 (stdlib), anthropic (Claude API), Pydantic  

## Key decisions
<!-- fill in as decisions are made during build sessions -->

## Next step
Read the research spec, then design the dual-layer memory schema (soft narrative + hard predicate layers).

## MVP definition
- `pip install worldoracle` works
- Dual-layer NPC memory: soft narrative layer (LLM-readable prose) + hard predicate layer (queryable facts)
- Contradiction checker that flags stale facts before LLM reasoning (sub-300ms)
- API: `worldoracle.assert_fact(predicate)`, `worldoracle.check(query)`, `worldoracle.reason(prompt)`
- Demo: assert "the king is alive," then "the king died at noon" → `check("is the king alive?")` flags the contradiction with both sources cited
- README with NPC memory architecture explanation and example
