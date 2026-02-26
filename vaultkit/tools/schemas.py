"""
Backward-compatible module.

If you previously imported:
  from vaultkit.tools.schemas import query_tool_schema

You can keep doing so, but these now generate *OpenAI* tools by default.

Prefer the new canonical definitions via:
  from vaultkit.tools.definitions import query_tool_def
  ToolBuilder(...).build(provider=ToolProvider.ANTHROPIC)
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .adapters.openai import to_openai_tool
from .definitions import (
    check_approval_tool_def,
    discover_tool_def,
    query_tool_def,
)


def discover_tool_schema(*, dataset_names: Optional[List[str]] = None) -> Dict[str, Any]:
    return to_openai_tool(discover_tool_def(dataset_names=dataset_names))


def query_tool_schema(
    *,
    dataset_names: Optional[List[str]] = None,
    schema_hints: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, Any]:
    return to_openai_tool(query_tool_def(dataset_names=dataset_names, schema_hints=schema_hints))


def check_approval_tool_schema() -> Dict[str, Any]:
    return to_openai_tool(check_approval_tool_def())
