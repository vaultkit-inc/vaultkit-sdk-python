from __future__ import annotations

from typing import Optional, Any

from .base import VaultKitError, ErrorContext


# generic categories

class ValidationError(VaultKitError):
    error_code = "validation_error"


class AuthError(VaultKitError):
    error_code = "auth_error"


class ForbiddenError(VaultKitError):
    error_code = "forbidden"


class NotFoundError(VaultKitError):
    error_code = "not_found"


class ConflictError(VaultKitError):
    error_code = "conflict"


class RateLimitError(VaultKitError):
    error_code = "rate_limited"
    retryable = True


class TransportError(VaultKitError):
    error_code = "transport_error"
    retryable = True


class ServerError(VaultKitError):
    error_code = "server_error"
    retryable = True


class ClientError(VaultKitError):
    error_code = "client_error"


# domain-specific (VaultKit)

class DeniedError(VaultKitError):
    """
    Raised when VaultKit policy denies a request.
    Do not retry — denial is deterministic.
    """

    error_code = "policy_denied"
    retryable = False

    def __init__(
        self,
        message: str,
        *,
        policy_id: Optional[str] = None,
        context: Optional[ErrorContext] = None,
    ) -> None:
        super().__init__(message, context=context)
        self.policy_id = policy_id


class QueuedError(VaultKitError):
    """
    Raised when a request is queued and the caller chose not to poll.
    """

    error_code = "queued"

    def __init__(
        self,
        message: str,
        *,
        request_id: Optional[str] = None,
        context: Optional[ErrorContext] = None,
    ) -> None:
        super().__init__(message, context=context)
        self.request_id = request_id


class ApprovalRequiredError(VaultKitError):
    """
    Raised when a request reaches pending_approval after polling.
    """

    error_code = "approval_required"

    def __init__(
        self,
        message: str,
        *,
        request_id: Optional[str] = None,
        context: Optional[ErrorContext] = None,
    ) -> None:
        super().__init__(message, context=context)
        self.request_id = request_id


class GrantExpiredError(VaultKitError):
    error_code = "grant_expired"

    def __init__(
        self,
        message: str,
        *,
        grant_ref: Optional[str] = None,
        context: Optional[ErrorContext] = None,
    ) -> None:
        super().__init__(message, context=context)
        self.grant_ref = grant_ref


class GrantRevokedError(VaultKitError):
    error_code = "grant_revoked"

    def __init__(
        self,
        message: str,
        *,
        grant_ref: Optional[str] = None,
        context: Optional[ErrorContext] = None,
    ) -> None:
        super().__init__(message, context=context)
        self.grant_ref = grant_ref


class PolicyBundleRevokedError(VaultKitError):
    """
    Unrecoverable — escalate to a VaultKit administrator.
    """

    error_code = "policy_bundle_revoked"
    retryable = False

    def __init__(
        self,
        message: str,
        *,
        bundle_checksum: Optional[str] = None,
        context: Optional[ErrorContext] = None,
    ) -> None:
        super().__init__(message, context=context)
        self.bundle_checksum = bundle_checksum


class PollTimeoutError(VaultKitError):
    """
    Polling exceeded timeout. Request may still be processing.
    """

    error_code = "poll_timeout"
    retryable = True  # caller can retry polling

    def __init__(
        self,
        message: str,
        *,
        request_id: Optional[str] = None,
        context: Optional[ErrorContext] = None,
    ) -> None:
        super().__init__(message, context=context)
        self.request_id = request_id


# HTTP mapping

def map_http_error(status_code: int, message: str, *, context: ErrorContext) -> VaultKitError:
    raw = context.raw if isinstance(context.raw, dict) else {}

    # future-proof: allow backend to send structured error types
    error_type = raw.get("type") if isinstance(raw, dict) else None

    if status_code == 400:
        return ValidationError(message, context=context)

    if status_code == 401:
        return AuthError(message, context=context)

    if status_code == 403:
        if error_type == "policy_denied":
            return DeniedError(
                message,
                policy_id=raw.get("policy_id"),
                context=context,
            )
        return ForbiddenError(message, context=context)

    if status_code == 404:
        return NotFoundError(message, context=context)

    if status_code == 409:
        return ConflictError(message, context=context)

    if status_code == 429:
        return RateLimitError(message, context=context)

    if 400 <= status_code < 500:
        return ClientError(message, context=context)

    if 500 <= status_code:
        return ServerError(message, context=context)

    return VaultKitError(message, context=context)
