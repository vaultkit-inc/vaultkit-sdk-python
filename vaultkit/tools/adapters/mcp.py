from __future__ import annotations

"""
MCP tool adapter.

Converts a canonical VaultKit tool definition into an ``mcp.types.Tool``,
exactly the way ``to_anthropic_tool`` and ``to_openai_tool`` convert into
their provider shapes.

Canonical shape (from vaultkit.tools.definitions):
    {"name": str, "description": str, "input_schema": {...}}

MCP shape (mcp.types.Tool):
    Tool(name=..., description=..., inputSchema={...})

The only real work is the ``input_schema`` -> ``inputSchema`` rename and
wrapping the dict in the MCP type. No governance logic lives here — this is
pure translation, the same as every other adapter in this package.
"""

from typing import Any, Dict

import mcp.types as types


def to_mcp_tool(canonical: Dict[str, Any]) -> types.Tool:
    """Convert one canonical tool def into an MCP Tool.

    Args:
        canonical: A dict with ``name``, ``description`` and ``input_schema``,
            as produced by ``vaultkit.tools.definitions``.

    Returns:
        An ``mcp.types.Tool`` suitable for returning from a ``list_tools``
        handler.
    """
    return types.Tool(
        name=canonical["name"],
        description=canonical.get("description"),
        inputSchema=canonical["input_schema"],
    )
