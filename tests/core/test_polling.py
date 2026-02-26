import pytest

from vaultkit.core.polling import poll_until_done, PollConfig
from vaultkit.models.query_result import QueryResult
from vaultkit.errors.exceptions import QueuedError, PollTimeoutError, NotFoundError


@pytest.fixture
def no_sleep(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda x: None)


@pytest.fixture
def no_jitter(monkeypatch):
    monkeypatch.setattr("random.uniform", lambda a, b: 0)


def make_result(status, request_id="req_1", grant_ref=None):
    return QueryResult(
        status=status,
        request_id=request_id,
        grant_ref=grant_ref,
    )


def test_returns_immediately_if_terminal():
    result = make_result("granted")

    out = poll_until_done(
        initial=result,
        poll_fn=lambda _: result,
        config=PollConfig(),
    )

    assert out is result


def test_missing_request_id_raises():
    result = QueryResult(status="queued", request_id=None)

    with pytest.raises(QueuedError):
        poll_until_done(
            initial=result,
            poll_fn=lambda _: result,
            config=PollConfig(),
        )


def test_poll_until_granted(no_sleep, no_jitter):
    responses = [
        make_result("queued"),
        make_result("granted", grant_ref="g1"),
    ]

    def poll_fn(_):
        return responses.pop(0)

    result = poll_until_done(
        initial=make_result("queued"),
        poll_fn=poll_fn,
        config=PollConfig(interval_s=0.01, timeout_s=1),
    )

    assert result.status == "granted"
    assert result.grant_ref == "g1"


def test_poll_until_denied(no_sleep, no_jitter):
    responses = [
        make_result("queued"),
        make_result("denied"),
    ]

    def poll_fn(_):
        return responses.pop(0)

    result = poll_until_done(
        initial=make_result("queued"),
        poll_fn=poll_fn,
        config=PollConfig(interval_s=0.01, timeout_s=1),
    )

    assert result.status == "denied"


def test_poll_until_pending_approval(no_sleep, no_jitter):
    responses = [
        make_result("queued"),
        make_result("pending_approval"),
    ]

    def poll_fn(_):
        return responses.pop(0)

    result = poll_until_done(
        initial=make_result("queued"),
        poll_fn=poll_fn,
        config=PollConfig(interval_s=0.01, timeout_s=1),
    )

    assert result.status == "pending_approval"


def test_not_found_error_becomes_timeout(no_sleep, no_jitter):
    def poll_fn(_):
        raise NotFoundError("not found")

    with pytest.raises(PollTimeoutError):
        poll_until_done(
            initial=make_result("queued"),
            poll_fn=poll_fn,
            config=PollConfig(interval_s=0.01, timeout_s=1),
        )


def test_timeout(no_sleep, no_jitter, monkeypatch):
    call_count = {"count": 0}

    def poll_fn(_):
        call_count["count"] += 1
        return make_result("queued")

    times = [0]

    def mock_time():
        return times[0]

    monkeypatch.setattr("time.time", mock_time)

    def advance_time():
        times[0] += 0.4

    monkeypatch.setattr("time.sleep", lambda x: advance_time())

    with pytest.raises(PollTimeoutError):
        poll_until_done(
            initial=make_result("queued"),
            poll_fn=poll_fn,
            config=PollConfig(interval_s=0.01, timeout_s=1),
        )

    assert call_count["count"] > 0


def test_approval_returns_immediately(no_sleep, no_jitter):
    def poll_fn(_):
        return make_result("pending_approval")

    result = poll_until_done(
        initial=make_result("queued"),
        poll_fn=poll_fn,
        config=PollConfig(),
    )

    assert result.status == "pending_approval"
