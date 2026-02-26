from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class QueryResult:
    status: str
    grant_ref: Optional[str] = None
    expires_at: Optional[str] = None

    masked_fields: List[str] = field(default_factory=list)
    rows: List[Dict[str, Any]] = field(default_factory=list)

    request_id: Optional[str] = None
    reason: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None

    policy_id: Optional[str] = None
    approver_role: Optional[str] = None

    correlation_id: Optional[str] = None  # propagated from HTTP layer

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "QueryResult":
        status = str(data.get("status") or "").lower().strip()

        if not status:
            raise ValueError("Missing 'status' in QueryResult response")

        request_id = data.get("request_id")

        if status in ("queued", "granted", "ok", "pending_approval") and not request_id:
            raise ValueError(f"Missing request_id for status '{status}'")

        return QueryResult(
            status=status,
            grant_ref=data.get("grant_ref") or data.get("grant_id"),
            expires_at=data.get("expires_at"),
            masked_fields=list(data.get("masked_fields") or []),
            rows=list(data.get("rows") or []),
            request_id=data.get("request_id"),
            reason=data.get("reason"),
            meta=data.get("meta"),
            policy_id=data.get("policy_id"),
            approver_role=data.get("approver_role"),
            correlation_id=data.get("correlation_id"),
        )

    @property
    def is_granted(self) -> bool:
        return self.status == "granted"

    @property
    def is_denied(self) -> bool:
        return self.status == "denied"

    @property
    def needs_approval(self) -> bool:
        return self.status in ("queued", "pending_approval")

    @property
    def is_pending(self) -> bool:
        return self.status in ("queued", "pending_approval")

    @property
    def is_terminal(self) -> bool:
        return self.status in ("granted", "denied")

    @property
    def has_data(self) -> bool:
        return bool(self.rows)
