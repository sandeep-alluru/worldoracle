"""Belief state diff between two points in time."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from worldoracle.store import WorldOracleStore


@dataclass
class BeliefChange:
    subject: str
    predicate: str
    old_value: str | None
    new_value: str | None
    old_confidence: float | None
    new_confidence: float | None
    change_type: str  # "added", "removed", "value_changed", "confidence_changed"


@dataclass
class BeliefDiff:
    before_count: int
    after_count: int
    changes: list[BeliefChange]
    added: int
    removed: int
    modified: int
    stable: int
    summary: str


def diff_belief_states(
    store: WorldOracleStore,
    before_timestamp: float,
    after_timestamp: float,
    subject: str | None = None,
) -> BeliefDiff:
    """Diff belief state at two points in time using the snapshots table."""
    conn = store._conn
    # Check if snapshots table exists
    tbl = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='belief_snapshots'"
    ).fetchone()
    if tbl is None:
        return BeliefDiff(0, 0, [], 0, 0, 0, 0, "No snapshot data available.")

    # Get latest belief for each (subject, attribute) before or at timestamp.
    # We first find the most-recent snapshot taken at or before `ts`, then
    # return only the beliefs that were recorded in that snapshot.
    def get_beliefs_at(ts: float) -> dict[tuple[str, str], tuple[Any, Any]]:
        snap_row = conn.execute(
            "SELECT snapshot_id FROM snapshot_registry WHERE taken_at <= ? "
            "ORDER BY taken_at DESC LIMIT 1",
            (ts,),
        ).fetchone()
        if snap_row is None:
            return {}
        snap_id = snap_row["snapshot_id"]
        if subject:
            sql = """
                SELECT subject, attribute, value, confidence
                FROM belief_snapshots
                WHERE snapshot_id=? AND subject=?
            """
            params: tuple[Any, ...] = (snap_id, subject)
        else:
            sql = """
                SELECT subject, attribute, value, confidence
                FROM belief_snapshots
                WHERE snapshot_id=?
            """
            params = (snap_id,)
        rows = conn.execute(sql, params).fetchall()
        return {(r["subject"], r["attribute"]): (r["value"], r["confidence"]) for r in rows}

    before_beliefs = get_beliefs_at(before_timestamp)
    after_beliefs = get_beliefs_at(after_timestamp)

    all_keys = set(before_beliefs.keys()) | set(after_beliefs.keys())
    changes = []
    stable = 0

    for subj, attr in all_keys:
        in_before = (subj, attr) in before_beliefs
        in_after = (subj, attr) in after_beliefs

        if in_before and not in_after:
            old_v, old_c = before_beliefs[(subj, attr)]
            changes.append(BeliefChange(subj, attr, old_v, None, old_c, None, "removed"))
        elif not in_before and in_after:
            new_v, new_c = after_beliefs[(subj, attr)]
            changes.append(BeliefChange(subj, attr, None, new_v, None, new_c, "added"))
        else:
            old_v, old_c = before_beliefs[(subj, attr)]
            new_v, new_c = after_beliefs[(subj, attr)]
            if old_v != new_v:
                changes.append(
                    BeliefChange(subj, attr, old_v, new_v, old_c, new_c, "value_changed")
                )
            elif abs(old_c - new_c) > 1e-9:
                changes.append(
                    BeliefChange(subj, attr, old_v, new_v, old_c, new_c, "confidence_changed")
                )
            else:
                stable += 1

    added = sum(1 for c in changes if c.change_type == "added")
    removed = sum(1 for c in changes if c.change_type == "removed")
    modified = sum(1 for c in changes if c.change_type in ("value_changed", "confidence_changed"))
    before_count = len(before_beliefs)
    after_count = len(after_beliefs)

    summary = (
        f"Before: {before_count} beliefs, After: {after_count} beliefs. "
        f"Added: {added}, Removed: {removed}, Modified: {modified}, Stable: {stable}."
    )
    return BeliefDiff(before_count, after_count, changes, added, removed, modified, stable, summary)
