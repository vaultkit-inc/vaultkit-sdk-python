from __future__ import annotations

"""
``vaultkit-mcp`` entrypoint.

    vaultkit-mcp                                   # stdio (default), local use
    vaultkit-mcp --transport http --port 8000      # hosted (not yet implemented)

stdio is the local transport: an MCP host (Claude Desktop, Cursor, ...) launches
this as a subprocess and pipes JSON-RPC over stdin/stdout. Credentials come from
the environment (see StdioClientResolver).

http (streamable HTTP) is the hosted transport. It is not wired up yet: it
requires the per-principal OAuth exchange in HttpClientResolver first.
"""

import argparse
import os
import sys
from typing import Optional

from .identity import HttpClientResolver, StdioClientResolver
from .server import McpServerConfig, build_server


def _config_from_env() -> McpServerConfig:
    def _flag(name: str, default: bool) -> bool:
        raw = os.environ.get(name)
        if raw is None:
            return default
        return raw.strip().lower() in ("1", "true", "yes", "on")

    return McpServerConfig(
        environment=os.environ.get("VAULTKIT_ENVIRONMENT", "production"),
        include_discover=_flag("VAULTKIT_MCP_INCLUDE_DISCOVER", True),
        include_query=_flag("VAULTKIT_MCP_INCLUDE_QUERY", True),
        include_check_approval=_flag("VAULTKIT_MCP_INCLUDE_CHECK_APPROVAL", True),
        fetch_schema_hints=_flag("VAULTKIT_MCP_SCHEMA_HINTS", True),
        default_purpose=os.environ.get("VAULTKIT_MCP_DEFAULT_PURPOSE"),
        default_requester_region=os.environ.get("VAULTKIT_MCP_DEFAULT_REGION"),
    )


async def _run_stdio(server) -> None:
    from mcp.server.stdio import stdio_server

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def _run_http(server, host: str, port: int) -> None:
    # Not implemented. Streamable HTTP requires a session manager and an ASGI
    # app, and — before that — the per-principal OAuth exchange in
    # HttpClientResolver. Reference for the intended wiring:
    #
    #   from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    #   import uvicorn
    #   from starlette.applications import Starlette
    #   ... mount the session manager, add OAuth token validation middleware,
    #       then uvicorn.run(app, host=host, port=port)
    raise NotImplementedError(
        "Hosted HTTP transport is not implemented yet. Implement "
        "HttpClientResolver (per-principal identity) first, then wire the "
        "streamable-HTTP ASGI app here. Use --transport stdio for now."
    )


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vaultkit-mcp",
        description="Expose VaultKit's governed tools over the Model Context Protocol.",
    )
    parser.add_argument(
        "--transport",
        choices=("stdio", "http"),
        default=os.environ.get("VAULTKIT_MCP_TRANSPORT", "stdio"),
        help="Transport to serve on (default: stdio).",
    )
    parser.add_argument("--host", default=os.environ.get("VAULTKIT_MCP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("VAULTKIT_MCP_PORT", "8000")))
    args = parser.parse_args(argv)

    try:
        import anyio
    except ImportError:
        print(
            "The MCP extra is not installed. Install it with:\n"
            "    pip install vaultkit[mcp]",
            file=sys.stderr,
        )
        return 1

    config = _config_from_env()

    if args.transport == "stdio":
        resolver = StdioClientResolver()
        server = build_server(resolver, config)
        try:
            anyio.run(_run_stdio, server)
        finally:
            resolver.close()
        return 0

    # http
    resolver = HttpClientResolver()
    server = build_server(resolver, config)
    _run_http(server, args.host, args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
