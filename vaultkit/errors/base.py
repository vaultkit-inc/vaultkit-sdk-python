from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class ErrorContext:
    status_code: Optional[int] = None
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None
    raw: Optional[Any] = None


class VaultKitError(Exception):
    """Base exception for VaultKit SDK."""

    error_code: str = "vaultkit_error"
    retryable: bool = False

    def __init__(self, message: str, *, context: Optional[ErrorContext] = None):
        super().__init__(message)
        self.message = message
        self.context = context or ErrorContext()

    def __str__(self) -> str:
        base = self.message
        if self.context and self.context.correlation_id:
            return f"{base} (correlation_id={self.context.correlation_id})"
        return base
