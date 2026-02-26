from __future__ import annotations

from typing import Any, Dict


def to_openai_tool(defn: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert canonical tool definition -> OpenAI 'tools' format.

    Canonical:
      { "name": str, "description": str, "input_schema": {...} }

    OpenAI:
      { "type": "function", "function": { "name": ..., "description": ..., "parameters": ... } }
    """
    return {
        "type": "function",
        "function": {
            "name": defn["name"],
            "description": defn.get("description", ""),
            "parameters": defn.get("input_schema", {"type": "object", "properties": {}}),
        },
    }
