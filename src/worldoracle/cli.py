"""CLI for worldoracle — NPC contradiction detector and belief repair."""

from __future__ import annotations

import click

from worldoracle.predicate import (
    BeliefRepairer,
    ContradictionDetector,
    WorldPredicate,
)
from worldoracle.report import print_beliefs, print_repairs
from worldoracle.store import WorldOracleStore


@click.group()
@click.version_option(package_name="worldoracle")
@click.option(
    "--db",
    default=".worldoracle/oracle.db",
    show_default=True,
    envvar="WORLDORACLE_DB",
    help="Path to the SQLite database.",
)
@click.pass_context
def main(ctx: click.Context, db: str) -> None:
    """NPC contradiction detector and belief repair for game worlds."""
    ctx.ensure_object(dict)
    ctx.obj["db"] = db


@main.command()
@click.argument("npc_id")
@click.argument("subject")
@click.argument("attribute")
@click.argument("value")
@click.option("--source", default="", help="Source of belief (e.g. 'observation', 'rumor')")
@click.option("--confidence", type=float, default=1.0, help="Belief confidence [0-1].")
@click.option("--timestamp", type=float, default=0.0, help="Belief timestamp (float).")
@click.pass_context
def add(
    ctx: click.Context,
    npc_id: str,
    subject: str,
    attribute: str,
    value: str,
    source: str,
    confidence: float,
    timestamp: float,
) -> None:
    """Add a predicate to an NPC's belief state."""
    store = WorldOracleStore(ctx.obj["db"])
    pred = WorldPredicate(
        subject=subject,
        attribute=attribute,
        value=value,
        source=source,
        confidence=confidence,
        timestamp=timestamp,
    )
    store.save_predicate(npc_id, pred)
    click.echo(f"Added predicate {pred.id} to {npc_id}: {subject}.{attribute}={value}")
    store.close()


@main.command()
@click.argument("npc_id")
@click.pass_context
def check(ctx: click.Context, npc_id: str) -> None:
    """Detect contradictions in NPC belief state."""
    store = WorldOracleStore(ctx.obj["db"])
    state = store.get_belief_state(npc_id)
    detector = ContradictionDetector()
    contradictions = detector.detect(state)
    if contradictions:
        click.echo(f"Found {len(contradictions)} contradiction(s) for {npc_id}:")
        for a, b in contradictions:
            click.echo(f"  CONFLICT: {a.subject}.{a.attribute}: {a.value!r} vs {b.value!r}")
    else:
        click.echo(f"No contradictions found for {npc_id}.")
    store.close()


@main.command()
@click.argument("npc_id")
@click.pass_context
def repair(ctx: click.Context, npc_id: str) -> None:
    """Generate repair frames for contradictions in NPC belief state."""
    store = WorldOracleStore(ctx.obj["db"])
    state = store.get_belief_state(npc_id)
    detector = ContradictionDetector()
    repairer = BeliefRepairer()
    contradictions = detector.detect(state)
    repairs = []
    for a, b in contradictions:
        frame = repairer.repair(a, b)
        store.save_repair(frame)
        repairs.append(frame)
    print_repairs(repairs)
    store.close()


@main.command()
@click.argument("npc_id")
@click.pass_context
def beliefs(ctx: click.Context, npc_id: str) -> None:
    """List all beliefs for an NPC."""
    store = WorldOracleStore(ctx.obj["db"])
    state = store.get_belief_state(npc_id)
    print_beliefs(state)
    store.close()


@main.command()
@click.pass_context
def status(ctx: click.Context) -> None:
    """Show database stats: NPCs tracked and belief counts."""
    store = WorldOracleStore(ctx.obj["db"])
    npc_ids = store.list_npc_ids()
    click.echo(f"NPCs tracked: {len(npc_ids)}")
    for npc_id in npc_ids:
        state = store.get_belief_state(npc_id)
        click.echo(f"  {npc_id}: {len(state.predicates)} beliefs")
    store.close()


@main.command("consistency")
@click.option("--repair", is_flag=True, default=False, help="Auto-repair contradictions")
@click.pass_context
def consistency_cmd(ctx: click.Context, repair: bool) -> None:
    """Run full consistency check across all NPCs."""
    store = WorldOracleStore(ctx.obj["db"])
    from worldoracle.consistency import full_consistency_check
    report = full_consistency_check(store, auto_repair=repair)
    click.echo(f"Total predicates: {report.total_predicates}")
    click.echo(f"Contradictions found: {report.contradictions_found}")
    click.echo(f"Repaired: {report.contradictions_repaired}")
    click.echo(f"Unresolved: {report.unresolved}")
    click.echo(f"Consistency score: {report.consistency_score:.2f}")
    if report.most_contested:
        click.echo(f"Most contested subjects: {', '.join(report.most_contested)}")
    for line in report.repair_summary:
        click.echo(f"  {line}")
    store.close()


@main.command("diff")
@click.option("--before", "before_ts", type=float, required=True, help="Before timestamp")
@click.option("--after", "after_ts", type=float, required=True, help="After timestamp")
@click.option("--subject", default=None, help="Filter by subject")
@click.pass_context
def diff_cmd(ctx: click.Context, before_ts: float, after_ts: float, subject: str | None) -> None:
    """Diff belief state at two points in time."""
    store = WorldOracleStore(ctx.obj["db"])
    from worldoracle.diff import diff_belief_states
    result = diff_belief_states(store, before_ts, after_ts, subject)
    click.echo(result.summary)
    for change in result.changes:
        click.echo(
            f"  [{change.change_type}] {change.subject}.{change.predicate}: "
            f"{change.old_value!r} -> {change.new_value!r}"
        )
    store.close()


if __name__ == "__main__":
    main()
