from .base import VaultKitError
from .exceptions import (
    ApprovalRequiredError,
    DeniedError,
    GrantExpiredError,
    GrantRevokedError,
    PolicyBundleRevokedError,
    PollTimeoutError,
    QueuedError,
    ValidationError,
    TransportError,
    ServerError,
    RateLimitError,
)

__all__ = [
    # Base
    "VaultKitError",

    # Domain (core VaultKit behavior)
    "DeniedError",
    "ApprovalRequiredError",
    "QueuedError",
    "GrantExpiredError",
    "GrantRevokedError",
    "PolicyBundleRevokedError",
    "PollTimeoutError",

    # User / validation
    "ValidationError",

    # Transport / infra
    "TransportError",
    "ServerError",
    "RateLimitError",
]