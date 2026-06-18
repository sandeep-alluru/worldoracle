"""MCP server for worldoracle.

Start:  python -m worldoracle.mcp_server
Or:     worldoracle-mcp

Add to Claude Desktop (~/.config/claude/claude_desktop_config.json):
    {
        "mcpServers": {
            "worldoracle": {
                "command": "worldoracle-mcp"
            }
        }
    }
"""

from __future__ import annotations

import sys
from typing import Any


def _require_mcp() -> Any:
    """Import MCP or exit with a helpful message."""
    try:
        import mcp
        import mcp.server.stdio
        import mcp.types as types
        from mcp.server import Server as _Server

        return mcp, types, _Server
    except ImportError:
        print(
            "MCP server requires: pip install 'worldoracle[mcp]'",
            file=sys.stderr,
        )
        sys.exit(1)


def run_server() -> None:
    """Start the MCP server on stdio."""
    mcp_mod, types, server_cls = _require_mcp()

    from worldoracle.predicate import (
        BeliefRepairer,
        ContradictionDetector,
        WorldPredicate,
    )
    from worldoracle.store import WorldOracleStore

    store = WorldOracleStore(":memory:")
    server = server_cls("worldoracle")

    @server.list_tools()
    async def list_tools() -> list[types.Tool]:
        """Expose worldoracle operations as MCP tools."""
        return [
            types.Tool(
                name="add_predicate",
                description="Add a belief predicate to an NPC's world model.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "npc_id": {"type": "string", "description": "NPC identifier"},
                        "subject": {"type": "string", "description": "Belief subject"},
                        "attribute": {"type": "string", "description": "Belief attribute"},
                        "value": {"description": "Belief value"},
                        "source": {"type": "string", "description": "Belief source"},
                        "confidence": {
                            "type": "number",
                            "description": "Confidence 0-1",
                            "default": 1.0,
                        },
                        "timestamp": {
                            "type": "number",
                            "description": "Timestamp",
                            "default": 0.0,
                        },
                    },
                    "required": ["npc_id", "subject", "attribute", "value"],
                },
            ),
            types.Tool(
                name="check_beliefs",
                description="Detect contradictions in an NPC's belief state.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "npc_id": {"type": "string", "description": "NPC identifier"},
                    },
                    "required": ["npc_id"],
                },
            ),
            types.Tool(
                name="repair_contradictions",
                description=(
                    "Generate repair frames for all contradictions in an NPC's belief state."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "npc_id": {"type": "string", "description": "NPC identifier"},
                    },
                    "required": ["npc_id"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(
        name: str, arguments: dict[str, Any]
    ) -> list[types.TextContent]:
        """Dispatch an MCP tool call."""
        if name == "add_predicate":
            pred = WorldPredicate(
                subject=arguments["subject"],
                attribute=arguments["attribute"],
                value=arguments["value"],
                source=arguments.get("source", ""),
                confidence=float(arguments.get("confidence", 1.0)),
                timestamp=float(arguments.get("timestamp", 0.0)),
            )
            store.save_predicate(arguments["npc_id"], pred)
            return [
                types.TextContent(
                    type="text",
                    text=f"Added predicate {pred.id} to {arguments['npc_id']}",
                )
            ]

        if name == "check_beliefs":
            npc_id = arguments["npc_id"]
            state = store.get_belief_state(npc_id)
            detector = ContradictionDetector()
            contradictions = detector.detect(state)
            if contradictions:
                lines = [f"Found {len(contradictions)} contradiction(s) for {npc_id}:"]
                for a, b in contradictions:
                    lines.append(
                        f"  CONFLICT {a.subject}.{a.attribute}: {a.value!r} vs {b.value!r}"
                    )
                return [types.TextContent(type="text", text="\n".join(lines))]
            return [
                types.TextContent(
                    type="text", text=f"No contradictions found for {npc_id}."
                )
            ]

        if name == "repair_contradictions":
            npc_id = arguments["npc_id"]
            state = store.get_belief_state(npc_id)
            detector = ContradictionDetector()
            repairer = BeliefRepairer()
            contradictions = detector.detect(state)
            repairs = []
            for a, b in contradictions:
                frame = repairer.repair(a, b)
                store.save_repair(frame)
                repairs.append(frame)
            if not repairs:
                return [types.TextContent(type="text", text="No repairs needed.")]
            lines = [f"Generated {len(repairs)} repair frame(s):"]
            for r in repairs:
                lines.append(f"  [{r.strategy}] resolved_value={r.resolved_value!r}: {r.reason}")
            return [types.TextContent(type="text", text="\n".join(lines))]

        raise ValueError(f"Unknown tool: {name}")

    import asyncio

    async def _main() -> None:
        async with mcp_mod.server.stdio.stdio_server() as (
            read_stream,
            write_stream,
        ):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    asyncio.run(_main())


if __name__ == "__main__":
    run_server()
