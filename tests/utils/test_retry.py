import pytest

from vaultkit.errors.exceptions import (
    ClientError,
    NotFoundError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from vaultkit.utils.retry import RetryConfig, with_retries

FAST = RetryConfig(max_attempts=3, base_sleep_s=0.0, max_sleep_s=0.0)


def _failing(exc):
    calls = []

    def fn():
        calls.append(1)
        raise exc

    return fn, calls


@pytest.mark.parametrize(
    "exc",
    [ValidationError("Unknown field `brand` on `payment_methods`."), NotFoundError("Dataset not found"),
     ClientError("conflict")],
)
def test_4xx_errors_are_not_retried(exc):
    fn, calls = _failing(exc)

    with pytest.raises(type(exc)):
        with_retries(fn, config=FAST)

    assert len(calls) == 1


@pytest.mark.parametrize("exc", [ServerError("Query engine error"), RateLimitError("slow down")])
def test_server_errors_and_rate_limits_are_retried(exc):
    fn, calls = _failing(exc)

    with pytest.raises(type(exc)):
        with_retries(fn, config=FAST)

    assert len(calls) == 3
