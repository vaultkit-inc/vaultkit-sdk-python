from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from vaultkit.core.http import HttpClient, HttpConfig
from vaultkit.core.polling import PollConfig, poll_until_done
from vaultkit.errors.exceptions import (
    ApprovalRequiredError,
    DeniedError,
    QueuedError,
    ValidationError,
)
from vaultkit.models.dataset_info import DatasetInfo
from vaultkit.models.dataset_schema import DatasetSchema
from vaultkit.models.fetch_result import FetchResult
from vaultkit.models.query_result import QueryResult
from vaultkit.utils.retry import RetryConfig, with_retries
from vaultkit.utils.validation import (
    require_str,
    validate_filters,
    validate_limit,
)


@dataclass(frozen=True)
class ClientConfig:
    # Use field(default_factory=...) to avoid Python mutable-default error
    http: HttpConfig = field(default_factory=HttpConfig)
    retries: RetryConfig = field(default_factory=RetryConfig)
    polling: PollConfig = field(default_factory=PollConfig)


class VaultKitClient:
    """
    VaultKit Python SDK.

    Two levels of abstraction:

    High-level (recommended for agents):
        execute()       Full lifecycle: intent → poll → fetch → data.
                        Grants are invisible. Agent gets data or a typed exception.

    Low-level (for custom orchestration):
        query()         Submit intent, get QueryResult (granted/queued/denied).
        fetch()         Redeem a grant_ref for data.
        poll()          Block until queued QueryResult reaches terminal state.
        poll_request()  Poll by request_id (used by check_approval flows).

    Discovery:
        datasets()      List authorized datasets from the registry.
        schema()        Get field-level schema for a dataset.
    """

    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        org: str,
        config: Optional[ClientConfig] = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self.base_url = require_str("base_url", base_url)
        self.token = require_str("token", token)
        self.org = require_str("org", org)
        self.config = config or ClientConfig()
        self._logger = logger

        self._http = HttpClient(
            base_url=self.base_url,
            token=self.token,
            config=self.config.http,
            logger=self._logger,
        )

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> "VaultKitClient":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # Internal helpers

    def _path(self, suffix: str) -> str:
        return f"/api/v1/orgs/{self.org}{suffix}"

    # High-level

    def execute(
        self,
        *,
        dataset: str,
        fields: Optional[List[str]] = None,
        filters: Optional[List[Dict[str, Any]]] = None,
        limit: Optional[int] = None,
        purpose: Optional[str] = None,
        requester_region: Optional[str] = None,
        requester_clearance: Optional[str] = None,
        poll_config: Optional[PollConfig] = None,
    ) -> FetchResult:
        """
        Submit an intent request and return data — full grant lifecycle internal.

        Raises:
            DeniedError             Policy rejected. Do not retry.
            ApprovalRequiredError   Needs human approval (request_id attached).
            PollTimeoutError        Approval polling exceeded configured timeout.
            GrantExpiredError / GrantRevokedError    Transient; re-submit.
            PolicyBundleRevokedError                Unrecoverable; escalate.
        """
        dataset = require_str("dataset", dataset)

        if self._logger:
            self._logger.info(
                "[VaultKit] Execute",
                extra={"dataset": dataset},
            )

        result = self.query(
            dataset=dataset,
            fields=fields,
            filters=filters,
            limit=limit,
            purpose=purpose,
            requester_region=requester_region,
            requester_clearance=requester_clearance,
            poll=True,
            poll_config=poll_config,
        )

        if result.needs_approval:
            if self._logger:
                self._logger.info(
                    "[VaultKit] Approval required",
                    extra={
                        "dataset": dataset,
                        "request_id": result.request_id,
                        "approver_role": result.approver_role,
                    },
                )

            raise ApprovalRequiredError(
                f"Dataset '{dataset}' requires human approval. "
                f"Approver role: {result.approver_role or 'unknown'}. "
                f"Use poll_request('{result.request_id}') to check status.",
                request_id=result.request_id,
            )

        if result.is_denied:
            if self._logger:
                self._logger.info(
                    "[VaultKit] Request denied",
                    extra={
                        "dataset": dataset,
                        "request_id": result.request_id,
                        "request_id": result.request_id or "none",
                        "policy_id": result.policy_id,
                    },
                )

            raise DeniedError(
                result.reason or "Request denied by policy",
                policy_id=result.policy_id,
            )

        # Case 1: data already returned (reuse path)
        if result.has_data and not result.grant_ref:
            if self._logger:
                self._logger.debug(
                    "[VaultKit] Reused request — returning data directly",
                    extra={
                        "dataset": dataset,
                        "request_id": result.request_id,
                    },
                )

            return FetchResult(
                rows=result.rows,
                meta=result.meta,
                correlation_id=result.correlation_id,
            )

        # Case 2: normal grant flow
        if result.grant_ref:
            return self.fetch(grant_ref=result.grant_ref)

        raise ValidationError(
            f"Unexpected state after polling: status={result.status}, no grant_ref or data."
        )

        if self._logger:
            self._logger.debug(
                "[VaultKit] Fetch after grant",
                extra={
                    "dataset": dataset,
                    "grant_ref": result.grant_ref,
                    "request_id": result.request_id,
                },
            )

        return self.fetch(grant_ref=result.grant_ref)

    # Low-level primitives

    def query(
        self,
        *,
        dataset: str,
        fields: Optional[List[str]] = None,
        filters: Optional[List[Dict[str, Any]]] = None,
        limit: Optional[int] = None,
        purpose: Optional[str] = None,
        requester_region: Optional[str] = None,
        requester_clearance: Optional[str] = None,
        poll: bool = False,
        poll_config: Optional[PollConfig] = None,
    ) -> QueryResult:
        dataset = require_str("dataset", dataset)
        limit = validate_limit(limit)
        filters = validate_filters(filters)

        req: Dict[str, Any] = {"dataset": dataset}
        body: Dict[str, Any] = {"request": req}

        if fields is not None:
            req["fields"] = list(fields)
        if limit is not None:
            req["limit"] = limit
        if purpose is not None:
            req["purpose"] = str(purpose)
        if filters is not None:
            req["filters"] = filters
        if requester_region is not None:
            body["requester_region"] = requester_region
        if requester_clearance is not None:
            body["requester_clearance"] = requester_clearance

        if self._logger:
            self._logger.debug(
                "[VaultKit] Submit intent",
                extra={
                    "dataset": dataset,
                    "poll": poll,
                    "has_fields": fields is not None,
                    "has_filters": filters is not None,
                    "limit": limit,
                },
            )

        def _do() -> QueryResult:
            data = self._http.post(
                self._path("/intent/requests"),
                json_body=body,
            )
            result = QueryResult.from_dict(data)

            if self._logger:
                self._logger.debug(
                    "[VaultKit] Intent response",
                    extra={
                        "dataset": dataset,
                        "status": result.status,
                        "request_id": result.request_id,
                        "policy_id": result.policy_id,
                    },
                )

            if result.is_denied:
                raise DeniedError(
                    result.reason or "Request denied",
                    policy_id=result.policy_id,
                )
            if result.is_pending and not poll:
                raise QueuedError(
                    "Request is queued. Set poll=True or call client.poll(result).",
                    request_id=result.request_id,
                )
            return result

        result = with_retries(_do, config=self.config.retries)

        if poll and result.is_pending:
            result = self.poll(result, config=poll_config)

        return result

    def fetch(self, *, grant_ref: str) -> FetchResult:
        grant_ref = require_str("grant_ref", grant_ref)

        if self._logger:
            self._logger.debug(
                "[VaultKit] Fetch",
                extra={"grant_ref": grant_ref},
            )

        def _do() -> FetchResult:
            data = self._http.post(
                self._path(f"/grants/{grant_ref}/fetch"),
                json_body={},
            )

            result = FetchResult.from_dict(data)

            if self._logger:
                self._logger.info(
                    "[VaultKit] Fetch complete",
                    extra={"grant_ref": grant_ref, "row_count": result.row_count},
                )

            return result

        return with_retries(_do, config=self.config.retries)

    def poll(
        self,
        result: QueryResult,
        *,
        config: Optional[PollConfig] = None,
    ) -> QueryResult:
        if not result.is_pending:
            return result

        cfg = config or self.config.polling

        if self._logger:
            self._logger.debug(
                "[VaultKit] Poll start",
                extra={
                    "request_id": result.request_id,
                    "status": result.status,
                    "timeout_s": cfg.timeout_s,
                },
            )

        def poll_fn(request_id: str) -> QueryResult:
          def _do() -> QueryResult:
              data = self._http.get(self._path(f"/requests/{request_id}"))
              return QueryResult.from_dict(data)

          return with_retries(_do, config=self.config.retries)

        return poll_until_done(
            initial=result,
            poll_fn=poll_fn,
            config=cfg,
            logger=self._logger,
        )

    def poll_request(self, *, request_id: str) -> QueryResult:
        """Poll by request_id directly — used by the check_approval tool flow."""
        request_id = require_str("request_id", request_id)

        if self._logger:
            self._logger.debug(
                "[VaultKit] Poll request",
                extra={"request_id": request_id},
            )

        def _do() -> QueryResult:
            data = self._http.get(self._path(f"/requests/{request_id}"))
            return QueryResult.from_dict(data)

        return with_retries(_do, config=self.config.retries)

    # Discovery

    def datasets(
        self,
        *,
        environment: str = "production",
        requester_region: Optional[str] = None,
        dataset_region: Optional[str] = None,
    ) -> List[DatasetInfo]:
        environment = require_str("environment", environment)
        params: Dict[str, Any] = {"environment": environment}
        if requester_region is not None:
            params["requester_region"] = requester_region
        if dataset_region is not None:
            params["dataset_region"] = dataset_region

        if self._logger:
            self._logger.debug(
                "[VaultKit] List datasets",
                extra={
                    "environment": environment,
                    "requester_region": requester_region,
                    "dataset_region": dataset_region,
                },
            )

        def _do() -> List[DatasetInfo]:
            data = self._http.get(self._path("/aql/datasets"), params=params)
            raw = data.get("datasets")
            if not isinstance(raw, list):
                raise ValidationError("Invalid datasets response: expected list")
            return [DatasetInfo.from_dict(d) for d in raw]

        return with_retries(_do, config=self.config.retries)

    def schema(
        self,
        dataset: str,
        *,
        environment: str = "production",
        requester_region: Optional[str] = None,
        dataset_region: Optional[str] = None,
    ) -> DatasetSchema:
        dataset = require_str("dataset", dataset)
        environment = require_str("environment", environment)
        params: Dict[str, Any] = {"environment": environment}
        if requester_region is not None:
            params["requester_region"] = requester_region
        if dataset_region is not None:
            params["dataset_region"] = dataset_region

        if self._logger:
            self._logger.debug(
                "[VaultKit] Get schema",
                extra={
                    "dataset": dataset,
                    "environment": environment,
                    "requester_region": requester_region,
                    "dataset_region": dataset_region,
                },
            )

        def _do() -> DatasetSchema:
            data = self._http.get(
                self._path(f"/aql/datasets/{dataset}/schema"),
                params=params,
            )
            if not isinstance(data, dict):
                raise ValidationError("Invalid schema response")
            return DatasetSchema.from_dict(data)

        return with_retries(_do, config=self.config.retries)
