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


if __name__ == "__main__":
    main()
