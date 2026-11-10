from __future__ import annotations

import time
import random
import logging
from dataclasses import dataclass
from typing import Callable, TypeVar, Optional

from vaultkit.errors.exceptions import BusyError, RateLimitError, TransportError, ServerError

T = TypeVar("T")

logger = logging.getLogger("vaultkit.retry")


@dataclass(frozen=True)
class RetryConfig:
    max_attempts: int = 3
    base_sleep_s: float = 0.5
    max_sleep_s: float = 4.0

    # Add jitter (±20%)
    jitter_ratio: float = 0.2

    # The longest Retry-After the SDK will wait for. A server asking for
    # longer gets a BusyError at once instead of blocking the caller.
    max_retry_after_s: float = 30.0


def retryable(exc: Exception) -> bool:
    return isinstance(exc, (RateLimitError, TransportError, ServerError)) and not isinstance(exc, BusyError)


def _retry_after(exc: Exception) -> Optional[float]:
    return getattr(getattr(exc, "context", None), "retry_after", None)


def _busy(exc: Exception) -> bool:
    """429, or a 503 that says when to come back: VaultKit at capacity."""
    status = getattr(getattr(exc, "context", None), "status_code", None)
    return isinstance(exc, RateLimitError) or (status == 503 and _retry_after(exc) is not None)


def _busy_error(exc: Exception, retry_after: Optional[float]) -> BusyError:
    wait = f" (the server asked to wait {retry_after:g}s)" if retry_after is not None else ""
    return BusyError(
        f"VaultKit is busy. Try again later{wait}.",
        retry_after=retry_after,
        context=getattr(exc, "context", None),
    )


def with_retries(
    fn: Callable[[], T],
    *,
    config: RetryConfig,
) -> T:
    attempt = 0
    sleep_s = config.base_sleep_s

    while True:
        attempt += 1

        try:
            return fn()

        except Exception as e:
            is_retryable = retryable(e)

            retry_after = _retry_after(e) if is_retryable else None
            # A wait longer than we'll block for: give up now, saying when to come back.
            if retry_after is not None and retry_after > config.max_retry_after_s and _busy(e):
                raise _busy_error(e, retry_after) from e

            if attempt >= config.max_attempts or not is_retryable:
                logger.debug(
                    "retry.exit",
                    extra={
                        "attempt": attempt,
                        "retryable": is_retryable,
                        "error_type": type(e).__name__,
                    },
                )
                if is_retryable and _busy(e):
                    raise _busy_error(e, retry_after) from e
                raise

            # Apply jitter
            jitter = random.uniform(
                -sleep_s * config.jitter_ratio,
                sleep_s * config.jitter_ratio,
            )

            sleep_time = min(
                max(0.0, sleep_s + jitter),
                config.max_sleep_s,
            )
            # Never sooner than the server asked; still backing off if it
            # keeps saying busy.
            if retry_after is not None:
                sleep_time = max(sleep_time, retry_after)

            logger.debug(
                "retry.sleep",
                extra={
                    "attempt": attempt,
                    "sleep_s": sleep_time,
                    "error_type": type(e).__name__,
                },
            )

            time.sleep(sleep_time)

            # Exponential backoff
            sleep_s = min(sleep_s * 2, config.max_sleep_s)
