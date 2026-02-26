from __future__ import annotations

from typing import Any, Dict


def to_anthropic_tool(defn: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert canonical tool definition -> Anthropic 'tools' format.

    Anthropic expects:
      { "name": str, "description": str, "input_schema": {...} }
    """
    return {
        "name": defn["name"],
        "description": defn.get("description", ""),
        "input_schema": defn.get("input_schema", {"type": "object", "properties": {}}),
    }