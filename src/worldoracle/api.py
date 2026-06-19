"""FastAPI REST wrapper for worldoracle.

Start:   uvicorn worldoracle.api:app --reload
Install: pip install "worldoracle[api]"
Docs:    http://localhost:8000/docs
"""

from __future__ import annotations

try:
    from fastapi import FastAPI
    from pydantic import BaseModel
except ImportError as exc:
    raise ImportError("API server requires: pip install 'worldoracle[api]'") from exc

from worldoracle.predicate import (
    BeliefRepairer,
    ContradictionDetector,
    WorldPredicate,
)
from worldoracle.store import WorldOracleStore

app = FastAPI(
    title="worldoracle API",
    description="NPC contradiction detector and belief repair for game worlds",
    version="0.1.0",
)

# In-memory store shared across requests (replace with file path in production)
_store = WorldOracleStore(":memory:")


# ── Models ────────────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    """Liveness probe response."""

    status: str
    version: str


class PredicateRequest(BaseModel):
    """Request body for adding a predicate."""

    npc_id: str
    subject: str
    attribute: str
    value: str
    source: str = ""
    confidence: float = 1.0
    timestamp: float = 0.0


class PredicateResponse(BaseModel):
    """Response after adding a predicate."""

    id: str
    npc_id: str
    subject: str
    attribute: str
    value: str
    source: str
    confidence: float
    timestamp: float


class ContradictionItem(BaseModel):
    """A single contradiction pair."""

    predicate_a_id: str
    predicate_b_id: str
    subject: str
    attribute: str
    value_a: str
    value_b: str


class RepairItem(BaseModel):
    """A single repair frame."""

    id: str
    predicate_a_id: str
    predicate_b_id: str
    strategy: str
    resolved_value: str
    reason: str
    timestamp: float


# ── Endpoints ─────────────────────────────────────────────────────────────────


@app.get("/health", response_model=HealthResponse)
async def health() -> dict[str, str]:
    """Liveness probe."""
    from worldoracle import __version__

    return {"status": "ok", "version": __version__}


@app.post("/predicate", response_model=PredicateResponse)
async def add_predicate(req: PredicateRequest) -> dict[str, object]:
    """Add a predicate to an NPC's belief state."""
    pred = WorldPredicate(
        subject=req.subject,
        attribute=req.attribute,
        value=req.value,
        source=req.source,
        confidence=req.confidence,
        timestamp=req.timestamp,
    )
    _store.save_predicate(req.npc_id, pred)
    return {
        "id": pred.id,
        "npc_id": req.npc_id,
        "subject": pred.subject,
        "attribute": pred.attribute,
        "value": str(pred.value),
        "source": pred.source,
        "confidence": pred.confidence,
        "timestamp": pred.timestamp,
    }


@app.get("/beliefs/{npc_id}")
async def get_beliefs(npc_id: str) -> dict[str, object]:
    """Return all beliefs for an NPC."""
    state = _store.get_belief_state(npc_id)
    return state.to_dict()


@app.post("/check/{npc_id}")
async def check_contradictions(npc_id: str) -> dict[str, object]:
    """Detect contradictions in an NPC's belief state."""
    state = _store.get_belief_state(npc_id)
    detector = ContradictionDetector()
    contradictions = detector.detect(state)
    items = [
        {
            "predicate_a_id": a.id,
            "predicate_b_id": b.id,
            "subject": a.subject,
            "attribute": a.attribute,
            "value_a": str(a.value),
            "value_b": str(b.value),
        }
        for a, b in contradictions
    ]
    return {"npc_id": npc_id, "contradictions": items, "count": len(items)}


@app.get("/repairs/{npc_id}")
async def get_repairs(npc_id: str) -> dict[str, object]:
    """Return all stored repair frames for an NPC's predicates."""
    state = _store.get_belief_state(npc_id)
    pred_ids = {p.id for p in state.predicates}
    all_repairs = _store.get_repairs()
    relevant = [
        r for r in all_repairs if r.predicate_a_id in pred_ids or r.predicate_b_id in pred_ids
    ]
    return {
        "npc_id": npc_id,
        "repairs": [r.to_dict() for r in relevant],
        "count": len(relevant),
    }


@app.post("/repair/{npc_id}")
async def repair_npc(npc_id: str) -> dict[str, object]:
    """Generate and store repair frames for an NPC's contradictions."""
    state = _store.get_belief_state(npc_id)
    detector = ContradictionDetector()
    repairer = BeliefRepairer()
    contradictions = detector.detect(state)
    if not contradictions:
        return {"npc_id": npc_id, "repairs": [], "count": 0}
    repairs = []
    for a, b in contradictions:
        frame = repairer.repair(a, b)
        _store.save_repair(frame)
        repairs.append(frame.to_dict())
    return {"npc_id": npc_id, "repairs": repairs, "count": len(repairs)}
