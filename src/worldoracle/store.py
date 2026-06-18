"""SQLite-backed store for worldoracle predicates, belief states, and repair frames."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from worldoracle.predicate import BeliefState, RepairFrame, WorldPredicate


class WorldOracleStore:
    """SQLite-backed persistence for WorldPredicates and RepairFrames."""

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS predicates (
        id TEXT PRIMARY KEY,
        npc_id TEXT NOT NULL,
        subject TEXT NOT NULL,
        attribute TEXT NOT NULL,
        value TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT '',
        confidence REAL NOT NULL DEFAULT 1.0,
        timestamp REAL NOT NULL DEFAULT 0.0
    );
    CREATE TABLE IF NOT EXISTS repairs (
        id TEXT PRIMARY KEY,
        predicate_a_id TEXT NOT NULL,
        predicate_b_id TEXT NOT NULL,
        strategy TEXT NOT NULL,
        resolved_value TEXT NOT NULL,
        reason TEXT NOT NULL,
        timestamp REAL NOT NULL DEFAULT 0.0
    );
    """

    def __init__(self, path: str | Path = ":memory:") -> None:
        """Open (or create) the store at *path*. Use ':memory:' for in-process use."""
        self.path = Path(path) if path != ":memory:" else None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        db_path = str(self.path) if self.path else ":memory:"
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(self._SCHEMA)
        self._conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    # ── Predicates ────────────────────────────────────────────────────────────

    def save_predicate(self, npc_id: str, pred: WorldPredicate) -> None:
        """Upsert a predicate for the given NPC."""
        self._conn.execute(
            "INSERT OR REPLACE INTO predicates VALUES (?,?,?,?,?,?,?,?)",
            (
                pred.id,
                npc_id,
                pred.subject,
                pred.attribute,
                json.dumps(pred.value),
                pred.source,
                pred.confidence,
                pred.timestamp,
            ),
        )
        self._conn.commit()

    def get_belief_state(self, npc_id: str) -> BeliefState:
        """Load all predicates for *npc_id* and return a BeliefState."""
        rows = self._conn.execute(
            "SELECT * FROM predicates WHERE npc_id=? ORDER BY timestamp",
            (npc_id,),
        ).fetchall()
        state = BeliefState(npc_id=npc_id)
        for row in rows:
            d = dict(row)
            p = WorldPredicate(
                subject=d["subject"],
                attribute=d["attribute"],
                value=json.loads(d["value"]),
                source=d["source"],
                confidence=d["confidence"],
                timestamp=d["timestamp"],
            )
            state.predicates.append(p)
        state._recompute_id()
        return state

    def list_npc_ids(self) -> list[str]:
        """Return all distinct NPC IDs in the store."""
        rows = self._conn.execute(
            "SELECT DISTINCT npc_id FROM predicates"
        ).fetchall()
        return [r[0] for r in rows]

    # ── Repairs ───────────────────────────────────────────────────────────────

    def save_repair(self, repair: RepairFrame) -> None:
        """Upsert a repair frame."""
        self._conn.execute(
            "INSERT OR REPLACE INTO repairs VALUES (?,?,?,?,?,?,?)",
            (
                repair.id,
                repair.predicate_a_id,
                repair.predicate_b_id,
                repair.strategy,
                json.dumps(repair.resolved_value),
                repair.reason,
                repair.timestamp,
            ),
        )
        self._conn.commit()

    def get_repairs(
        self,
        predicate_a_id: str = "",
        predicate_b_id: str = "",
    ) -> list[RepairFrame]:
        """Return repair frames, optionally filtered by predicate ID."""
        if predicate_a_id or predicate_b_id:
            rows = self._conn.execute(
                "SELECT * FROM repairs WHERE predicate_a_id=? OR predicate_b_id=?",
                (predicate_a_id, predicate_b_id),
            ).fetchall()
        else:
            rows = self._conn.execute("SELECT * FROM repairs").fetchall()
        result = []
        for row in rows:
            d = dict(row)
            r = RepairFrame(
                predicate_a_id=d["predicate_a_id"],
                predicate_b_id=d["predicate_b_id"],
                strategy=d["strategy"],
                resolved_value=json.loads(d["resolved_value"]),
                reason=d["reason"],
                timestamp=d["timestamp"],
            )
            result.append(r)
        return result
