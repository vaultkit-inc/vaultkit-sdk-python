from __future__ import annotations

from enum import Enum


class ToolProvider(str, Enum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    RAW = "raw"


__all__ = ["ToolProvider"]
