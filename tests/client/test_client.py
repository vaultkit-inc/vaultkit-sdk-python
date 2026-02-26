import pytest
from unittest.mock import MagicMock

from vaultkit.client import VaultKitClient
from vaultkit.models.query_result import QueryResult
from vaultkit.models.fetch_result import FetchResult
from vaultkit.errors.exceptions import (
    ApprovalRequiredError,
    DeniedError,
    QueuedError,
    TransportError,
    ServerError,
)


@pytest.fixture
def client():
    c = VaultKitClient(
        base_url="http://test",
        token="token",
        org="org",
    )
    c._http = MagicMock()
    return c


def make_query_result(**overrides):
    base = {
        "status": "granted",
        "request_id": "req_1",
        "grant_ref": "grant_123",
        "rows": [],
        "meta": {},
        "correlation_id": "corr_1",
        "policy_id": None,
        "reason": None,
        "approver_role": None,
    }
    base.update(overrides)
    return QueryResult.from_dict(base)


def make_fetch_result():
    return FetchResult.from_dict({
        "rows": [{"id": 1}],
        "meta": {},
        "correlation_id": "corr_1",
    })


def test_execute_success_with_grant(client):
    query_result = make_query_result(grant_ref="grant_123")

    client.query = MagicMock(return_value=query_result)
    client.fetch = MagicMock(return_value=make_fetch_result())

    result = client.execute(dataset="users")

    assert result.rows == [{"id": 1}]
    client.fetch.assert_called_once_with(grant_ref="grant_123")


def test_execute_returns_data_directly(client):
    query_result = make_query_result(
        grant_ref=None,
        rows=[{"id": 1}],
    )

    client.query = MagicMock(return_value=query_result)

    result = client.execute(dataset="users")

    assert result.rows == [{"id": 1}]


def test_execute_approval_required(client):
    query_result = make_query_result(
        status="queued",
        approver_role="admin",
    )

    client.query = MagicMock(return_value=query_result)

    with pytest.raises(ApprovalRequiredError):
        client.execute(dataset="users")


def test_execute_denied(client):
    query_result = make_query_result(
        status="denied",
        reason="policy block",
    )

    client.query = MagicMock(return_value=query_result)

    with pytest.raises(DeniedError):
        client.execute(dataset="users")


def test_query_success(client):
    client._http.post.return_value = {
        "status": "granted",
        "request_id": "req_1",
        "grant_ref": "grant_123",
    }

    result = client.query(dataset="users")

    assert result.grant_ref == "grant_123"


def test_query_queued_without_poll_raises(client):
    client._http.post.return_value = {
        "status": "queued",
        "request_id": "req_1",
    }

    with pytest.raises(QueuedError):
        client.query(dataset="users", poll=False)


def test_query_denied_raises(client):
    client._http.post.return_value = {
        "status": "denied",
        "request_id": "req_1",
        "policy_id": "p1",
        "reason": "blocked",
    }

    with pytest.raises(DeniedError):
        client.query(dataset="users")


def test_query_with_poll_calls_poll(client):
    client._http.post.return_value = {
        "status": "queued",
        "request_id": "req_1",
    }

    client.poll = MagicMock(return_value=make_query_result())

    result = client.query(dataset="users", poll=True)

    client.poll.assert_called_once()
    assert result.status == "granted"


def test_query_missing_request_id_raises(client):
    client._http.post.return_value = {
        "status": "queued",
    }

    with pytest.raises(ValueError):
        client.query(dataset="users")


def test_query_builds_correct_payload(client):
    client._http.post.return_value = {
        "status": "granted",
        "request_id": "r1",
        "grant_ref": "g1",
    }

    client.query(
        dataset="users",
        fields=["id"],
        limit=10,
        filters=[{"field": "id", "op": "eq", "value": 1}],
    )

    args, kwargs = client._http.post.call_args

    assert "/intent/requests" in args[0]

    body = kwargs["json_body"]
    assert body["request"]["dataset"] == "users"
    assert body["request"]["fields"] == ["id"]
    assert body["request"]["limit"] == 10
    assert body["request"]["filters"] == [{"field": "id", "op": "eq", "value": 1}]


def test_fetch_success(client):
    client._http.post.return_value = {
        "rows": [{"id": 1}],
        "meta": {},
        "correlation_id": "c1",
    }

    result = client.fetch(grant_ref="grant_123")

    assert result.rows == [{"id": 1}]
    assert result.row_count == 1


def test_fetch_handles_invalid_rows_shape(client):
    client._http.post.return_value = {
        "rows": "invalid",
        "meta": "invalid",
    }

    result = client.fetch(grant_ref="g1")

    assert result.rows == []
    assert result.meta is None


def test_fetch_retries_on_transport_error(client):
    calls = []

    def side_effect(*args, **kwargs):
        if len(calls) < 1:
            calls.append(1)
            raise TransportError("network")
        return {
            "rows": [{"id": 1}],
            "meta": {},
        }

    client._http.post.side_effect = side_effect

    result = client.fetch(grant_ref="g1")

    assert result.rows == [{"id": 1}]
    assert len(calls) == 1


def test_query_propagates_http_errors(client):
    client._http.post.side_effect = ServerError("boom")

    with pytest.raises(ServerError):
        client.query(dataset="users")


def test_poll_skips_if_not_pending(client):
    result = make_query_result(status="granted")

    output = client.poll(result)

    assert output == result


def test_poll_calls_poll_until_done(client, monkeypatch):
    result = make_query_result(status="queued")

    mock_poll = MagicMock(return_value=make_query_result())

    monkeypatch.setattr(
        "vaultkit.client.poll_until_done",
        mock_poll,
    )

    output = client.poll(result)

    mock_poll.assert_called_once()
    assert output.status == "granted"


def test_poll_request_calls_http(client):
    client._http.get.return_value = {
        "status": "granted",
        "request_id": "req_1",
    }

    result = client.poll_request(request_id="req_1")

    assert result.status == "granted"


def test_datasets_invalid_shape_raises(client):
    client._http.get.return_value = {
        "datasets": "not-a-list"
    }

    with pytest.raises(Exception):
        client.datasets()


def test_schema_invalid_response_raises(client):
    client._http.get.return_value = "invalid"

    with pytest.raises(Exception):
        client.schema("users")


def test_context_manager_closes_client():
    client = VaultKitClient(
        base_url="http://test",
        token="token",
        org="org",
    )

    client._http = MagicMock()

    with client:
        pass

    client._http.close.assert_called_once()
