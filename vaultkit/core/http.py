from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional, Callable
import logging

import httpx

from vaultkit.errors.base import ErrorContext
from vaultkit.errors.exceptions import map_http_error, TransportError


@dataclass(frozen=True)
class HttpConfig:
    timeout_s: float = 15.0
    user_agent: str = "vaultkit-python/1.0"


class HttpClient:
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        config: Optional[HttpConfig] = None,
        retry_fn: Optional[Callable[[Callable[[], httpx.Response]], httpx.Response]] = None,
        logger: Optional[logging.Logger] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.config = config or HttpConfig()
        self._client = httpx.Client(timeout=self.config.timeout_s)
        self._retry_fn = retry_fn  # optional retry wrapper
        self._logger = logger

        self._default_headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": self.config.user_agent,
        }

    def close(self) -> None:
        self._client.close()

    # public API

    def get(
        self,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return self._request("GET", path, params=params)

    def post(
        self,
        path: str,
        *,
        json_body: Dict[str, Any],
    ) -> Dict[str, Any]:
        return self._request("POST", path, json=json_body)

    # internal

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"

        if self._logger:
            self._logger.debug(
                "[VaultKit] HTTP request",
                extra={
                    "method": method,
                    "path": path,
                },
            )

        def send() -> httpx.Response:
            return self._client.request(
                method,
                url,
                headers=self._default_headers,
                params=params,
                json=json,
            )

        try:
            res = self._retry_fn(send) if self._retry_fn else send()
            return self._handle(res, method=method, path=path)
        except httpx.RequestError as e:
            if self._logger:
                self._logger.error(
                    "[VaultKit] Network error",
                    extra={
                        "method": method,
                        "path": path,
                        "error": str(e),
                    },
                )

            raise TransportError(
                f"Network error: {e}",
                context=ErrorContext(raw=str(e)),
            ) from e

    def _handle(self, res: httpx.Response, *, method: str, path: str) -> Dict[str, Any]:
        correlation_id = (
            res.headers.get("x-correlation-id")
            or res.headers.get("correlation_id")
        )

        if self._logger:
            self._logger.debug(
                "[VaultKit] HTTP response",
                extra={
                    "method": method,
                    "path": path,
                    "status_code": res.status_code,
                    "correlation_id": correlation_id,
                },
            )

        # success
        if 200 <= res.status_code < 300:
            if not res.content:
                return {}

            try:
                data = res.json()
            except Exception as e:
                if self._logger:
                    self._logger.error(
                        "[VaultKit] Invalid JSON response",
                        extra={
                            "status_code": res.status_code,
                            "correlation_id": correlation_id,
                        },
                    )

                raise TransportError(
                    "Invalid JSON response from VaultKit",
                    context=ErrorContext(
                        status_code=res.status_code,
                        correlation_id=correlation_id,
                        raw=res.text,
                    ),
                ) from e

            return data if isinstance(data, dict) else {"data": data}

        # error
        raw: Any = None
        msg = f"VaultKit API error ({res.status_code})"

        try:
            raw = res.json()
            if isinstance(raw, dict):
                msg = (
                    raw.get("error")
                    or raw.get("message")
                    or raw.get("detail")
                    or msg
                )
        except Exception:
            raw = res.text

        if self._logger:
            self._logger.error(
                "[VaultKit] API error",
                extra={
                    "status_code": res.status_code,
                    "correlation_id": correlation_id,
                    "message": msg,
                },
            )

        ctx = ErrorContext(
            status_code=res.status_code,
            correlation_id=correlation_id,
            raw=raw,
        )

        raise map_http_error(res.status_code, msg, context=ctx)
