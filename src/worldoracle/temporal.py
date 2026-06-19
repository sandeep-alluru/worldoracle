"""Temporal belief tracking — snapshots and history."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass

from worldoracle.store import WorldOracleStore


@dataclass
class BeliefSnapshot:
    timestamp: float
    subject: str
    predicate: str   # this is the attribute field
    value: str
    confidence: float
    source: str


class TemporalBeliefStore:
    """Track how beliefs change over time using a separate snapshots table."""

    def __init__(self, store: WorldOracleStore) -> None:
        self._store = store
        self._conn = store._conn
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS belief_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                snapshot_id INTEGER NOT NULL,
                snapshot_ts REAL NOT NULL,
                npc_id TEXT NOT NULL,
                subject TEXT NOT NULL,
                attribute TEXT NOT NULL,
                value TEXT NOT NULL,
                confidence REAL NOT NULL,
                source TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS snapshot_registry (
                snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                taken_at REAL NOT NULL
            );
        """)
        self._conn.commit()

    def record_snapshot(self) -> int:
        """Record current belief state as a timestamped snapshot. Returns snapshot ID.

        Raises RuntimeError if the database fails to assign a row ID.
        """
        now = time.time()
        cur = self._conn.execute(
            "INSERT INTO snapshot_registry (taken_at) VALUES (?)", (now,)
        )
        snap_id = cur.lastrowid
        if snap_id is None:
            raise RuntimeError("Failed to insert snapshot registry row: no rowid returned")
        # Get all current predicates
        rows = self._conn.execute("SELECT * FROM predicates").fetchall()
        for row in rows:
            self._conn.execute(
                """INSERT INTO belief_snapshots
                   (snapshot_id, snapshot_ts, npc_id, subject, attribute, value, confidence, source)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (snap_id, now, row["npc_id"], row["subject"], row["attribute"],
                 row["value"], row["confidence"], row["source"]),
            )
        self._conn.commit()
        return snap_id

    @staticmethod
    def _deserialize_value(v: str) -> str:
        """Deserialize a stored value, handling JSON-encoded strings."""
        try:
            return json.loads(v)  # type: ignore[return-value]
        except (json.JSONDecodeError, ValueError):
            return v

    def get_belief_at(
        self, subject: str, predicate: str, timestamp: float
    ) -> BeliefSnapshot | None:
        """Get a belief snapshot at or before the given timestamp."""
        row = self._conn.execute(
            """SELECT * FROM belief_snapshots
               WHERE subject=? AND attribute=? AND snapshot_ts <= ?
               ORDER BY snapshot_ts DESC LIMIT 1""",
            (subject, predicate, timestamp),
        ).fetchone()
        if row is None:
            return None
        return BeliefSnapshot(
            timestamp=row["snapshot_ts"],
            subject=row["subject"],
            predicate=row["attribute"],
            value=self._deserialize_value(row["value"]),
            confidence=row["confidence"],
            source=row["source"],
        )

    def get_belief_history(self, subject: str, predicate: str) -> list[BeliefSnapshot]:
        """Full history of a belief, newest first."""
        rows = self._conn.execute(
            """SELECT * FROM belief_snapshots
               WHERE subject=? AND attribute=?
               ORDER BY snapshot_ts DESC""",
            (subject, predicate),
        ).fetchall()
        result = []
        for row in rows:
            result.append(BeliefSnapshot(
                timestamp=row["snapshot_ts"],
                subject=row["subject"],
                predicate=row["attribute"],
                value=self._deserialize_value(row["value"]),
                confidence=row["confidence"],
                source=row["source"],
            ))
        return result

    def belief_drift(self, subject: str, predicate: str) -> float:
        """Measure how much a belief's confidence has changed. 0=stable, 1=volatile."""
        history = self.get_belief_history(subject, predicate)
        if len(history) < 2:
            return 0.0
        confidences = [h.confidence for h in history]
        max_c = max(confidences)
        min_c = min(confidences)
        return min(1.0, max_c - min_c)
