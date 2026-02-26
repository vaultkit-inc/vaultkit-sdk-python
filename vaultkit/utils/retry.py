from __future__ import annotations

import time
import random
import logging
from dataclasses import dataclass
from typing import Callable, TypeVar, Optional

from vaultkit.errors.exceptions import RateLimitError, TransportError, ServerError

T = TypeVar("T")

logger = logging.getLogger("vaultkit.retry")


@dataclass(frozen=True)
class RetryConfig:
    max_attempts: int = 3
    base_sleep_s: float = 0.5
    max_sleep_s: float = 4.0

    # Add jitter (±20%)
    jitter_ratio: float = 0.2


def retryable(exc: Exception) -> bool:
    return isinstance(exc, (RateLimitError, TransportError, ServerError))


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

            if attempt >= config.max_attempts or not is_retryable:
                logger.debug(
                    "retry.exit",
                    extra={
                        "attempt": attempt,
                        "retryable": is_retryable,
                        "error_type": type(e).__name__,
                    },
                )
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
