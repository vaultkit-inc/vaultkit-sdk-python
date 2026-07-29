from __future__ import annotations

"""
Identity resolution for the MCP server.

A single interface, ``ClientResolver``, turns an incoming request into a
``VaultKitClient``. This is the only part of the MCP layer that differs between
deployments, which lets ``server.py`` be written once and run in either mode:

    stdio  -> StdioClientResolver : one principal, read from env at startup.
    http   -> HttpClientResolver  : one principal per authenticated request.

The request handlers depend only on the ``ClientResolver`` interface and never
know which implementation they received.
"""

import os
from typing import Any, Optional

from vaultkit.client import VaultKitClient


class ClientResolver:
    """Resolve an incoming request context into a VaultKitClient.

    ``ctx`` is whatever the transport provides: ``None`` for stdio, or an
    authenticated request context for http. Implementations use as much of it
    as they need.
    """

    def resolve(self, ctx: Optional[Any] = None) -> VaultKitClient:  # pragma: no cover
        raise NotImplementedError

    def close(self) -> None:  # pragma: no cover
        pass


class StdioClientResolver(ClientResolver):
    """Single-principal resolver for local (stdio) use.

    Reads credentials from the environment once and returns the same client for
    every call. Over stdio there is a single caller (the host process that
    launched the server), so there is a single principal, and ``ctx`` is
    ignored.

    Required environment variables:
        VAULTKIT_BASE_URL
        VAULTKIT_TOKEN
        VAULTKIT_ORG
    """

    def __init__(
        self,
        *,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        org: Optional[str] = None,
    ) -> None:
        self._base_url = base_url or os.environ.get("VAULTKIT_BASE_URL")
        self._token = token or os.environ.get("VAULTKIT_TOKEN")
        self._org = org or os.environ.get("VAULTKIT_ORG")

        missing = [
            name
            for name, val in (
                ("VAULTKIT_BASE_URL", self._base_url),
                ("VAULTKIT_TOKEN", self._token),
                ("VAULTKIT_ORG", self._org),
            )
            if not val
        ]
        if missing:
            raise RuntimeError(
                "Missing required VaultKit credentials for the MCP server: "
                + ", ".join(missing)
                + ". Set them in the environment (or your MCP host's server "
                "config 'env' block) before starting vaultkit-mcp."
            )

        self._client: Optional[VaultKitClient] = None

    def resolve(self, ctx: Optional[Any] = None) -> VaultKitClient:
        if self._client is None:
            self._client = VaultKitClient(
                base_url=self._base_url,  # type: ignore[arg-type]
                token=self._token,  # type: ignore[arg-type]
                org=self._org,  # type: ignore[arg-type]
            )
        return self._client

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None


class HttpClientResolver(ClientResolver):
    """Per-principal resolver for hosted (streamable-HTTP) use.

    Not yet implemented. Over http each request may belong to a different
    principal, so a client cannot be built once at startup; it must be resolved
    per request from the authenticated identity.

    Intended implementation:
        1. Read the bearer token from ``ctx`` (the request's auth context).
        2. Resolve it to a (token, org) principal, delegating to the control
           plane rather than trusting client-supplied claims.
        3. Construct and return a VaultKitClient for that principal.
        4. Optionally cache clients per principal and close idle ones.
    """

    def resolve(self, ctx: Optional[Any] = None) -> VaultKitClient:
        raise NotImplementedError(
            "Hosted HTTP identity resolution is not implemented yet. "
            "Run the server with --transport stdio, or implement "
            "HttpClientResolver.resolve to exchange the request's OAuth token "
            "for a VaultKit principal via the control plane."
        )
