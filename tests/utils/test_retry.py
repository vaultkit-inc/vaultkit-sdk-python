from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

import pytest

from vaultkit.core.http import parse_retry_after
from vaultkit.errors.base import ErrorContext
from vaultkit.errors.exceptions import (
    BusyError,
    ClientError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from vaultkit.utils import retry as retry_module
from vaultkit.utils.retry import RetryConfig, with_retries

FAST = RetryConfig(max_attempts=3, base_sleep_s=0.0, max_sleep_s=0.0)


@pytest.fixture
def sleeps(monkeypatch):
    slept = []
    monkeypatch.setattr(retry_module.time, "sleep", slept.append)
    return slept


def _failing(*excs):
    """Raises each exception in turn (the last one forever)."""
    calls = []

    def fn():
        calls.append(1)
        raise excs[min(len(calls), len(excs)) - 1]

    return fn, calls


def _rate_limited(retry_after=None):
    return RateLimitError("Too many requests", context=ErrorContext(status_code=429, retry_after=retry_after))


@pytest.mark.parametrize(
    "exc",
    [ValidationError("Unknown field `brand` on `payment_methods`."), NotFoundError("Dataset not found"),
     ClientError("conflict")],
)
def test_4xx_errors_are_not_retried(exc, sleeps):
    fn, calls = _failing(exc)

    with pytest.raises(type(exc)):
        with_retries(fn, config=FAST)

    assert len(calls) == 1
    assert sleeps == []


def test_server_errors_are_retried(sleeps):
    fn, calls = _failing(ServerError("Query engine error"))

    with pytest.raises(ServerError):
        with_retries(fn, config=FAST)

    assert len(calls) == 3


def test_429_waits_as_long_as_retry_after_says_then_stops_with_a_busy_error(sleeps):
    fn, calls = _failing(_rate_limited(retry_after=2))

    with pytest.raises(BusyError) as err:
        with_retries(fn, config=FAST)

    assert len(calls) == 3
    assert sleeps == [2, 2]
    assert err.value.retry_after == 2
    assert str(err.value) == "VaultKit is busy. Try again later (the server asked to wait 2s)."


def test_429_without_retry_after_backs_off_and_stops_with_a_busy_error(sleeps):
    fn, calls = _failing(_rate_limited())
    config = RetryConfig(max_attempts=3, base_sleep_s=0.5, max_sleep_s=4.0, jitter_ratio=0.0)

    with pytest.raises(BusyError, match=r"^VaultKit is busy\. Try again later\.$"):
        with_retries(fn, config=config)

    assert len(calls) == 3
    assert sleeps == [0.5, 1.0]


def test_429_that_clears_returns_the_result(sleeps):
    calls = []

    def fn():
        calls.append(1)
        if len(calls) < 2:
            raise _rate_limited(retry_after=1)
        return "rows"

    assert with_retries(fn, config=FAST) == "rows"
    assert sleeps == [1]


def test_a_retry_after_longer_than_we_block_for_gives_up_at_once(sleeps):
    fn, calls = _failing(_rate_limited(retry_after=120))

    with pytest.raises(BusyError) as err:
        with_retries(fn, config=FAST)

    assert len(calls) == 1
    assert sleeps == []
    assert err.value.retry_after == 120


def test_a_503_with_retry_after_is_busy_too(sleeps):
    busy = ServerError("Query engine is busy, retry shortly", context=ErrorContext(status_code=503, retry_after=1))
    fn, calls = _failing(busy)

    with pytest.raises(BusyError):
        with_retries(fn, config=FAST)

    assert sleeps == [1, 1]


def test_parse_retry_after():
    assert parse_retry_after("3") == 3.0
    assert parse_retry_after(" 1.5 ") == 1.5
    assert parse_retry_after(None) is None
    assert parse_retry_after("soon") is None

    later = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=10), usegmt=True)
    assert 8 <= parse_retry_after(later) <= 10
