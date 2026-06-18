"""Output formatters for worldoracle: rich tables, JSON, and Markdown."""

from __future__ import annotations

import json

from rich.console import Console
from rich.table import Table

from worldoracle.predicate import BeliefState, RepairFrame

_console = Console()


def print_beliefs(state: BeliefState, console: Console | None = None) -> None:
    """Print a belief state as a rich table."""
    con = console or _console
    table = Table(title=f"Beliefs: {state.npc_id}", show_header=True)
    table.add_column("Subject")
    table.add_column("Attribute")
    table.add_column("Value")
    table.add_column("Source")
    table.add_column("Confidence")
    for p in state.predicates:
        table.add_row(
            p.subject,
            p.attribute,
            str(p.value),
            p.source,
            f"{p.confidence:.2f}",
        )
    con.print(table)


def print_repairs(
    repairs: list[RepairFrame], console: Console | None = None
) -> None:
    """Print a list of repair frames as a rich table, or a 'no repairs' message."""
    con = console or _console
    if not repairs:
        con.print("[green]No repairs needed.[/green]")
        return
    table = Table(title="Repair Frames", show_header=True)
    table.add_column("ID")
    table.add_column("Strategy")
    table.add_column("Resolved Value")
    table.add_column("Reason")
    for r in repairs:
        table.add_row(r.id, r.strategy, str(r.resolved_value), r.reason)
    con.print(table)


def to_json(
    state: BeliefState, repairs: list[RepairFrame] | None = None
) -> str:
    """Serialize a BeliefState (and optional repairs) to JSON."""
    data = state.to_dict()
    if repairs is not None:
        data["repairs"] = [r.to_dict() for r in repairs]
    return json.dumps(data, indent=2)


def to_markdown(states: list[BeliefState]) -> str:
    """Render a list of BeliefStates as a Markdown report."""
    lines = ["# worldoracle Belief Report", ""]
    for state in states:
        lines.append(f"## NPC: {state.npc_id}")
        lines.append("")
        lines.append("| Subject | Attribute | Value | Source | Confidence |")
        lines.append("|---------|-----------|-------|--------|------------|")
        for p in state.predicates:
            lines.append(
                f"| {p.subject} | {p.attribute} | {p.value} | {p.source} | {p.confidence:.2f} |"
            )
        lines.append("")
    return "\n".join(lines)
