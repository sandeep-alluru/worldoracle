"""Tests for the worldoracle FastAPI server."""

from __future__ import annotations

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")


@pytest.fixture
def client():  # type: ignore[return]
    """Return a FastAPI TestClient with a fresh in-memory store."""
    # Re-import to reset the in-memory store by reloading the module

    from fastapi.testclient import TestClient

    import worldoracle.api as api_mod

    # Reset the shared store between tests
    from worldoracle.store import WorldOracleStore

    api_mod._store = WorldOracleStore(":memory:")
    return TestClient(api_mod.app)


def test_health_returns_200(client) -> None:  # type: ignore[no-untyped-def]
    """GET /health should return 200 with status=ok."""
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_post_predicate(client) -> None:  # type: ignore[no-untyped-def]
    """POST /predicate should store a belief and return 200."""
    r = client.post(
        "/predicate",
        json={
            "npc_id": "guard-1",
            "subject": "king",
            "attribute": "alive",
            "value": "True",
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["subject"] == "king"
    assert "id" in body


def test_get_beliefs(client) -> None:  # type: ignore[no-untyped-def]
    """GET /beliefs/{npc_id} should return the NPC's belief state."""
    client.post(
        "/predicate",
        json={"npc_id": "guard-1", "subject": "king", "attribute": "alive", "value": "True"},
    )
    r = client.get("/beliefs/guard-1")
    assert r.status_code == 200
    body = r.json()
    assert body["npc_id"] == "guard-1"
    assert len(body["predicates"]) == 1


def test_check_contradictions(client) -> None:  # type: ignore[no-untyped-def]
    """POST /check/{npc_id} should detect contradictions."""
    client.post(
        "/predicate",
        json={"npc_id": "guard-1", "subject": "king", "attribute": "alive", "value": "True"},
    )
    client.post(
        "/predicate",
        json={"npc_id": "guard-1", "subject": "king", "attribute": "alive", "value": "False"},
    )
    r = client.post("/check/guard-1")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1


def test_get_repairs(client) -> None:  # type: ignore[no-untyped-def]
    """GET /repairs/{npc_id} should return repair frames after /repair."""
    client.post(
        "/predicate",
        json={
            "npc_id": "guard-1", "subject": "king", "attribute": "alive",
            "value": "True", "confidence": 0.5,
        },
    )
    client.post(
        "/predicate",
        json={
            "npc_id": "guard-1", "subject": "king", "attribute": "alive",
            "value": "False", "confidence": 0.9,
        },
    )
    # Trigger repair
    client.post("/repair/guard-1")
    r = client.get("/repairs/guard-1")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] >= 1


def test_get_beliefs_empty_npc(client) -> None:  # type: ignore[no-untyped-def]
    """GET /beliefs/{npc_id} for unknown NPC should return empty predicates."""
    r = client.get("/beliefs/nobody")
    assert r.status_code == 200
    body = r.json()
    assert body["npc_id"] == "nobody"
    assert body["predicates"] == []
