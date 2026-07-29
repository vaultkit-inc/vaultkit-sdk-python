from __future__ import annotations

"""
VaultKit MCP server (the ``[mcp]`` extra).

This subpackage exposes VaultKit's governed tools over the Model Context
Protocol so any MCP host (Claude Desktop, Cursor, custom agents) can query
governed data.

No policy evaluation happens here. This layer advertises tools by reusing
``ToolBuilder`` and dispatches calls by reusing ``ToolExecutor``. Every policy
decision, mask, grant and audit entry is performed by the control plane.

Two deployments share one codebase:
    - stdio  : one principal from environment variables (local use).
    - http   : one principal per authenticated session (not yet implemented;
               see identity.HttpClientResolver).

The only difference between them is how the caller's identity is resolved into
a VaultKitClient; everything else is shared.

Install:
    pip install vaultkit[mcp]

Run:
    vaultkit-mcp                 # stdio (default)
    vaultkit-mcp --transport http --host 0.0.0.0 --port 8000   # not yet implemented
"""

from .server import McpServerConfig, build_server

__all__ = ["McpServerConfig", "build_server"]
