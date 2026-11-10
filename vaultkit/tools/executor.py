# vaultkit/tools/executor.py
from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional

from vaultkit.errors.base import VaultKitError
from vaultkit.errors.exceptions import (
    ApprovalRequiredError,
    BusyError,
    ClientError,
    DeniedError,
    GrantExpiredError,
    GrantRevokedError,
    NotFoundError,
    PolicyBundleRevokedError,
    QueuedError,
    ValidationError,
)

if TYPE_CHECKING:
    from vaultkit.client import VaultKitClient


class ToolExecutor:
    """
    Provider-agnostic dispatcher for tool calls -> VaultKitClient methods.

    Any agent runtime can use this as long as it can provide:
      - tool_name: str
      - tool_args: dict

    Example (pseudo):
        name = tool_call["name"]
        args = tool_call["args"]
        result = executor.execute(name, args)
    """

    def __init__(
        self,
        client: "VaultKitClient",
        *,
        default_purpose: Optional[str] = None,
        default_requester_region: Optional[str] = None,
    ) -> None:
        self._client = client
        self._default_purpose = default_purpose
        self._default_requester_region = default_requester_region

    def execute(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch a tool call. Always returns a dict — never raises."""
        try:
            if tool_name == "vaultkit_discover":
                return self._execute_discover(tool_args)
            if tool_name == "vaultkit_describe":
                return self._execute_describe(tool_args)
            if tool_name == "vaultkit_query":
                return self._execute_query(tool_args)
            if tool_name == "vaultkit_check_approval":
                return self._execute_check_approval(tool_args)

            return self._error(
                f"Unknown tool '{tool_name}'. "
                "Available: vaultkit_discover, vaultkit_describe, vaultkit_query, vaultkit_check_approval.",
                code="unknown_tool",
            )
        except Exception as e:
            return self._translate_error(e)

    # dispatch

    def _execute_discover(self, args: Dict[str, Any]) -> Dict[str, Any]:
        environment = args.get("environment", "production")
        requester_region = args.get("requester_region")
        dataset_region = args.get("dataset_region")

        datasets = self._client.datasets(
            environment=environment,
            requester_region=requester_region,
            dataset_region=dataset_region,
        )

        visibility_map = {
            "allow": "accessible",
            "mask": "accessible, some fields masked",
            "require_approval": "requires approval",
            "deny": "not accessible",
        }

        return {
            "status": "ok",
            "datasets": [
                {
                    "name": d.dataset,
                    "datasource": d.datasource,
                    "visibility": visibility_map.get(getattr(d, "visibility", None), getattr(d, "visibility", None)),
                }
                for d in datasets
            ],
            "count": len(datasets),
        }

    def _execute_describe(self, args: Dict[str, Any]) -> Dict[str, Any]:
        dataset = args.get("dataset")
        if not dataset:
            return self._error("'dataset' is required for vaultkit_describe.", code="validation_error")

        schema = self._client.schema(dataset)

        fields = []
        for f in schema.fields:
            if not isinstance(f, dict) or not f.get("name"):
                continue
            access = f.get("visibility") or "allow"
            field: Dict[str, Any] = {"name": f["name"], "type": f.get("type"), "access": access}
            if access == "require_approval" and f.get("approver_roles"):
                field["approvers"] = f["approver_roles"]
            if f.get("masked"):
                # Masked whatever the decision: approval doesn't unmask.
                field["masked"] = f.get("mask") or True
            if f.get("tenant_column"):
                field["note"] = "your tenant; filtered automatically"
            fields.append(field)

        response: Dict[str, Any] = {
            "status": "ok",
            "dataset": schema.dataset,
            "fields": fields,
            "note": (
                "Use these exact field names in vaultkit_query. A field needing approval lists its approvers: "
                "every one of them must sign off. Masked fields return '*****', even after approval, and can't "
                "be filtered, grouped, sorted or aggregated (count is fine)."
            ),
        }
        if schema.visibility:
            response["access"] = schema.visibility
        if schema.tenant_scoped:
            response["tenant_scoped"] = True
        return response

    def _execute_query(self, args: Dict[str, Any]) -> Dict[str, Any]:
        dataset = args.get("dataset")
        if not dataset:
            return self._error("'dataset' is required for vaultkit_query.", code="validation_error")

        purpose = args.get("purpose") or self._default_purpose

        result = self._client.execute(
            dataset=dataset,
            fields=args.get("fields"),
            filters=args.get("filters"),
            limit=args.get("limit"),
            aggregates=args.get("aggregates"),
            group_by=args.get("group_by"),
            having=args.get("having"),
            order_by=args.get("order_by"),
            purpose=purpose,
            requester_region=args.get("requester_region") or self._default_requester_region,
        )

        response: Dict[str, Any] = {
            "status": "ok",
            "dataset": dataset,
            "row_count": result.row_count,
            "data": result.data,
        }

        if result.masked_fields:
            response["masked_fields"] = result.masked_fields
            response["note"] = f"Fields {result.masked_fields} were masked per data policy."

        return response

    def _execute_check_approval(self, args: Dict[str, Any]) -> Dict[str, Any]:
        request_id = args.get("request_id")
        if not request_id:
            return self._error("'request_id' is required for vaultkit_check_approval.", code="validation_error")

        poll_result = self._client.poll_request(request_id=request_id)

        if poll_result.is_granted and poll_result.grant_ref:
            fetch = self._client.fetch(grant_ref=poll_result.grant_ref)
            return {
                "status": "approved",
                "row_count": fetch.row_count,
                "data": fetch.data,
                "masked_fields": fetch.masked_fields,
            }

        if poll_result.is_denied:
            return {"status": "denied", "reason": poll_result.reason or "Approval was denied."}

        return {
            "status": "pending",
            "message": "Approval is still pending. Try again shortly.",
            "request_id": request_id,
        }

    # error translation

    def _translate_error(self, exc: Exception) -> Dict[str, Any]:
        msg = str(exc)
        error_code = getattr(exc, "error_code", "error")

        if isinstance(exc, DeniedError):
            policy_id = getattr(exc, "policy_id", None)
            reason = getattr(exc, "reason", None) or exc.message
            extra = f" (policy_id={policy_id})" if policy_id else ""
            return {
                "status": "denied",
                "reason": reason,
                "policy_id": policy_id,
                "error": (
                    f"Access denied by VaultKit policy{extra}. Reason: {reason}. "
                    "Do not retry — this denial is deterministic."
                ),
            }

        if isinstance(exc, ApprovalRequiredError):
            return {
                "status": "pending_approval",
                "message": (
                    "This request requires human approval. "
                    f"Use vaultkit_check_approval with request_id='{exc.request_id}' to check status."
                ),
                "request_id": exc.request_id,
            }

        if isinstance(exc, (GrantExpiredError, GrantRevokedError)):
            return self._error(
                f"{msg} Re-submit your query to get a fresh grant.",
                code=error_code,
            )

        if isinstance(exc, PolicyBundleRevokedError):
            return self._error(
                "The VaultKit policy bundle has been revoked. "
                "No data access is possible. Escalate to your VaultKit administrator.",
                code="bundle_revoked",
            )

        # The request was refused as written (an unknown field, a bad
        # filter): the server's message says what to fix. Fix the request
        # rather than retry it.
        if isinstance(exc, BusyError):
            response = {"status": "busy", "error": exc.message}
            if exc.retry_after is not None:
                response["retry_after_s"] = exc.retry_after
            return response

        if isinstance(exc, ValidationError):
            return self._client_error(exc, code="validation_error")

        # Any other 4xx (not found, conflict, forbidden, …): the server's
        # message as it is, under the error's own code.
        status_code = getattr(getattr(exc, "context", None), "status_code", None)
        if isinstance(exc, (NotFoundError, ClientError)) or (
            isinstance(exc, VaultKitError) and status_code and 400 <= status_code < 500
        ):
            return self._client_error(exc, code=error_code)

        if isinstance(exc, QueuedError):
            return {"status": "queued", "message": msg, "request_id": exc.request_id}

        return self._error(f"Unexpected error: {type(exc).__name__}: {msg}", code=error_code)

    # helpers

    @staticmethod
    def _client_error(exc: Exception, *, code: str) -> Dict[str, Any]:
        # exc.message, not str(exc): no correlation id appended to the text.
        response: Dict[str, Any] = {"status": code, "error": getattr(exc, "message", str(exc))}
        request_id = getattr(getattr(exc, "context", None), "request_id", None)
        if request_id:
            response["request_id"] = request_id
        return response

    @staticmethod
    def _error(message: str, *, code: str = "error") -> Dict[str, Any]:
        return {"status": code, "error": message}
