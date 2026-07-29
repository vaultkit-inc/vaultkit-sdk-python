from __future__ import annotations

"""
The VaultKit MCP server.

Two handlers, both thin:

    list_tools  -> reuse ToolBuilder to advertise the caller's authorized tools.
    call_tool   -> reuse ToolExecutor to run a call and return its result.

This uses the low-level ``mcp.server.lowlevel.Server`` rather than the
``@mcp.tool`` decorator API because the decorator registers a static tool list
at startup, whereas VaultKit's tool list is per-principal: different callers are
authorized for different datasets. ``list_tools`` therefore has to be computed
per session, which the low-level API allows.

The VaultKit SDK is synchronous (blocking HTTP and polling), while MCP handlers
are async. Blocking work is offloaded to a worker thread via
``anyio.to_thread.run_sync`` so it does not stall the event loop. This is
required once multiple callers can be served concurrently, and harmless for the
single-caller stdio case.
"""

import json
from dataclasses import dataclass
from typing import List, Optional

import anyio
import mcp.types as types
from mcp.server.lowlevel import Server

from vaultkit.tools.adapters import ToolProvider
from vaultkit.tools.adapters.mcp import to_mcp_tool
from vaultkit.tools.builder import ToolBuilder
from vaultkit.tools.executor import ToolExecutor

from .identity import ClientResolver


@dataclass
class McpServerConfig:
    """Server-wide configuration (not per-call; per-call args come from the agent)."""

    environment: str = "production"
    include_discover: bool = True
    include_query: bool = True
    # check_approval is exposed by default: the approval flow is asynchronous,
    # so the agent needs a way to poll a pending request to completion.
    include_check_approval: bool = True
    # Schema hints feed the agent the exact valid field names per dataset, which
    # guards against field-name hallucination. Keep on unless a very large
    # catalog makes startup slow.
    fetch_schema_hints: bool = True
    # Optional fallbacks if an agent omits them (agents normally supply purpose).
    default_purpose: Optional[str] = None
    default_requester_region: Optional[str] = None
    server_name: str = "vaultkit"


def build_server(resolver: ClientResolver, config: Optional[McpServerConfig] = None) -> Server:
    """Wire a low-level MCP Server around the given identity resolver.

    Args:
        resolver: Turns a request context into a VaultKitClient, and thereby
            determines whether this is a single-principal (stdio) or
            per-principal (http) server.
        config: Server-wide options. Defaults are suitable for local (stdio) use.

    Returns:
        A configured ``mcp.server.lowlevel.Server`` ready to run over any
        transport.
    """
    cfg = config or McpServerConfig()
    server: Server = Server(cfg.server_name)

    @server.list_tools()
    async def _list_tools() -> List[types.Tool]:
        # Resolve the caller -> client, then build their authorized tool list.
        # RAW gives canonical defs; those are mapped to MCP Tools by to_mcp_tool.
        client = resolver.resolve(_current_ctx(server))

        def _build():
            builder = ToolBuilder(client)
            return builder.build(
                provider=ToolProvider.RAW,
                environment=cfg.environment,
                include_discover=cfg.include_discover,
                include_query=cfg.include_query,
                include_check_approval=cfg.include_check_approval,
                fetch_schema_hints=cfg.fetch_schema_hints,
            )

        canonical = await anyio.to_thread.run_sync(_build)
        return [to_mcp_tool(t) for t in canonical]

    @server.call_tool()
    async def _call_tool(name: str, arguments: dict) -> List[types.ContentBlock]:
        # Resolve the caller -> client, then dispatch through the executor.
        # The executor never raises: denials, pending-approval and masking all
        # come back as a structured dict with a `status` field, which is
        # forwarded verbatim. A policy denial is a valid governed answer, not a
        # protocol error, so it is not raised or marked isError.
        client = resolver.resolve(_current_ctx(server))

        def _run():
            executor = ToolExecutor(
                client,
                default_purpose=cfg.default_purpose,
                default_requester_region=cfg.default_requester_region,
            )
            return executor.execute(name, arguments or {})

        result = await anyio.to_thread.run_sync(_run)
        text = json.dumps(result, default=str, ensure_ascii=False, indent=2)
        return [types.TextContent(type="text", text=text)]

    return server


def _current_ctx(server: Server):
    """Return the active request context, or None if there is none.

    stdio resolvers ignore this. The http resolver uses it to reach the
    authenticated identity. Accessing ``request_context`` outside a request
    raises, so it is guarded to keep the single-principal case working.
    """
    try:
        return server.request_context
    except Exception:
        return None
