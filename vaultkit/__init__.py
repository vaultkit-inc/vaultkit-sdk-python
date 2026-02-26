"""
VaultKit Python SDK

Quick start:

    from vaultkit import VaultKitClient

    with VaultKitClient(
        base_url="https://vaultkit.yourorg.com",
        token="your-jwt-token",
        org="your-org-id",
    ) as client:

        # High-level: full lifecycle, grants invisible
        result = client.execute(
            dataset="customers",
            fields=["id", "email", "revenue"],
            filters=[{"field": "revenue", "operator": "gt", "value": 10000}],
            purpose="Q4 revenue analysis",
        )

        # For AI agents — scoped tool schemas from the live registry:
        from vaultkit.tools import ToolBuilder, ToolExecutor

        tools = ToolBuilder(client).build()
        executor = ToolExecutor(client)
"""

from .client import ClientConfig, VaultKitClient

from .errors import (
    ApprovalRequiredError,
    DeniedError,
    GrantExpiredError,
    GrantRevokedError,
    PolicyBundleRevokedError,
    PollTimeoutError,
    QueuedError,
    ValidationError,
    VaultKitError,
    TransportError,
    ServerError,
    RateLimitError,
)

from .models import (
    DatasetInfo,
    DatasetSchema,
    FetchResult,
    QueryResult,
)

# Optional (nice DX improvement)
from .tools import ToolBuilder, ToolExecutor

__version__ = "0.1.0"

__all__ = [
    "VaultKitClient",
    "ClientConfig",

    # Models
    "QueryResult",
    "FetchResult",
    "DatasetInfo",
    "DatasetSchema",

    # Errors
    "VaultKitError",
    "DeniedError",
    "ApprovalRequiredError",
    "QueuedError",
    "GrantExpiredError",
    "GrantRevokedError",
    "PolicyBundleRevokedError",
    "ValidationError",
    "PollTimeoutError",
    "TransportError",
    "ServerError",
    "RateLimitError",

    # Tools
    "ToolBuilder",
    "ToolExecutor",
]