from __future__ import annotations

import time
import random
import logging
from dataclasses import dataclass
from typing import Callable, Optional

from vaultkit.errors.exceptions import QueuedError, PollTimeoutError, NotFoundError
from vaultkit.models.query_result import QueryResult

_TERMINAL_STATUSES = {"granted", "denied", "pending_approval"}
_APPROVAL_STATUSES = {"queued", "pending_approval"}


@dataclass(frozen=True)
class PollConfig:
    interval_s: float = 2.0
    timeout_s: float = 60.0

    # Approval-specific backoff (long waits expected)
    approval_backoff_factor: float = 1.5
    approval_max_interval_s: float = 15.0

    # Jitter percentage (±10% by default)
    jitter_ratio: float = 0.1


def poll_until_done(
    *,
    initial: QueryResult,
    poll_fn: Callable[[str], QueryResult],
    config: PollConfig,
    logger: Optional[logging.Logger] = None,
) -> QueryResult:
    # If already in a terminal state, return immediately
    if initial.status in _TERMINAL_STATUSES:
        if logger:
            logger.debug(
                "[VaultKit] Poll skipped (already terminal)",
                extra={"status": initial.status, "request_id": initial.request_id},
            )
        return initial

    if not initial.request_id:
        raise QueuedError(
            "Request is queued but no request_id was provided; cannot poll safely."
        )

    request_id = initial.request_id
    deadline = time.time() + config.timeout_s

    current = initial
    interval = config.interval_s
    attempt = 0

    while time.time() < deadline:
        attempt += 1

        # Apply jitter to avoid thundering herd issues when many requests are queued
        jitter = random.uniform(
            -interval * config.jitter_ratio,
            interval * config.jitter_ratio,
        )
        sleep_time = max(0.0, interval + jitter)

        # Ensure we don't sleep past the deadline
        remaining = deadline - time.time()
        if remaining <= 0:
            break

        if logger:
            logger.debug(
                "[VaultKit] Polling request",
                extra={
                    "request_id": request_id,
                    "attempt": attempt,
                    "interval": round(interval, 2),
                },
            )

        time.sleep(min(sleep_time, remaining))

        try:
            current = poll_fn(request_id)
        except NotFoundError:
            # Request disappeared (expired / deleted / invalid)
            if logger:
                logger.error(
                    "[VaultKit] Request not found during polling",
                    extra={"request_id": request_id},
                )
            raise PollTimeoutError(
                "Request not found while polling",
                request_id=request_id,
            )

        if logger:
            logger.debug(
                "[VaultKit] Poll result",
                extra={
                    "request_id": request_id,
                    "status": current.status,
                },
            )

        # If we've reached a terminal state, return result
        if current.status in _TERMINAL_STATUSES:
            if logger:
                logger.info(
                    "[VaultKit] Polling complete",
                    extra={
                        "request_id": request_id,
                        "status": current.status,
                    },
                )
            return current

        # Adjust interval based on status
        if current.status in _APPROVAL_STATUSES:
            # Slow down polling for approvals
            interval = min(
                interval * config.approval_backoff_factor,
                config.approval_max_interval_s,
            )
        else:
            # Reset to default interval for active processing states
            interval = config.interval_s

    # Timeout reached
    if logger:
        logger.error(
            "[VaultKit] Polling timed out",
            extra={"request_id": request_id},
        )

    raise PollTimeoutError(
        f"Request still queued after {config.timeout_s:.0f}s",
        request_id=request_id,
    )
