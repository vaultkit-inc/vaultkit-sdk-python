from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class FetchResult:
    rows: List[Dict[str, Any]]
    meta: Optional[Dict[str, Any]] = None
    correlation_id: Optional[str] = None

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "FetchResult":
        rows = data.get("rows") or []
        if not isinstance(rows, list):
            rows = []

        meta = data.get("meta")
        if not isinstance(meta, dict):
            meta = None

        return FetchResult(
            rows=rows,
            meta=meta,
            correlation_id=data.get("correlation_id"),
        )

    # Compatibility properties for client and executor — these are the standard names that
    # client and executor expect, but we can also have aliases for them if needed.

    @property
    def data(self) -> List[Dict[str, Any]]:
        """Alias for rows — used by executor and client."""
        return self.rows

    @property
    def row_count(self) -> int:
        """Row count derived from rows length."""
        return len(self.rows)

    @property
    def masked_fields(self) -> List[str]:
        """
        Masked field names from meta, if your API returns them there.
        Returns [] safely if meta is absent or has no masked_fields key.
        """
        value = (self.meta or {}).get("masked_fields")
        return value if isinstance(value, list) else []

    @property
    def is_empty(self) -> bool:
        return not self.rows
