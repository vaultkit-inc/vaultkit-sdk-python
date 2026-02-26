import pytest

from vaultkit.client import VaultKitClient
from vaultkit.errors.exceptions import ApprovalRequiredError, PollTimeoutError


class MockVaultKitServer:
    def __init__(
        self,
        *,
        intent_response,
        poll_responses=None,
        fetch_response=None,
    ):
        self.intent_response = intent_response
        self.poll_responses = poll_responses or []
        self.fetch_response = fetch_response or {}
        self._poll_index = 0

    def post(self, path, *args, **kwargs):
        if path.endswith("/intent/requests"):
            return self.intent_response

        if "/grants/" in path and path.endswith("/fetch"):
            return self.fetch_response

        return {}

    def get(self, path, *args, **kwargs):
        if "/requests/" in path:
            if self._poll_index < len(self.poll_responses):
                res = self.poll_responses[self._poll_index]
                self._poll_index += 1
                return res
            return self.poll_responses[-1] if self.poll_responses else {}

        return {}


@pytest.fixture
def client():
    c = VaultKitClient(
        base_url="http://test",
        token="token",
        org="org",
    )
    return c


def test_full_execute_flow(client, monkeypatch):
    request_id = "req_123"
    grant_ref = "grant_123"

    server = MockVaultKitServer(
        intent_response={
            "status": "queued",
            "request_id": request_id,
        },
        poll_responses=[
            {"status": "queued", "request_id": request_id},
            {"status": "granted", "request_id": request_id, "grant_ref": grant_ref},
        ],
        fetch_response={
            "rows": [{"id": 1, "name": "test"}],
            "meta": {"masked_fields": []},
            "correlation_id": "corr_1",
        },
    )

    client._http.post = server.post
    client._http.get = server.get

    def mock_poll_until_done(*, initial, poll_fn, config, logger):
        current = initial
        while True:
            current = poll_fn(request_id)
            if current.status in ("granted", "denied", "pending_approval"):
                return current

    monkeypatch.setattr(
        "vaultkit.client.poll_until_done",
        mock_poll_until_done,
    )

    result = client.execute(dataset="users")

    assert result.rows == [{"id": 1, "name": "test"}]
    assert result.row_count == 1
    assert result.correlation_id == "corr_1"


def test_full_flow_approval_required(client, monkeypatch):
    request_id = "req_123"

    server = MockVaultKitServer(
        intent_response={
            "status": "queued",
            "request_id": request_id,
        },
        poll_responses=[
            {"status": "pending_approval", "request_id": request_id},
        ],
    )

    client._http.post = server.post
    client._http.get = server.get

    def mock_poll_until_done(*, initial, poll_fn, config, logger):
        return poll_fn(request_id)

    monkeypatch.setattr(
        "vaultkit.client.poll_until_done",
        mock_poll_until_done,
    )

    with pytest.raises(ApprovalRequiredError):
        client.execute(dataset="users")


def test_full_flow_timeout(client, monkeypatch):
    request_id = "req_123"

    server = MockVaultKitServer(
        intent_response={
            "status": "queued",
            "request_id": request_id,
        },
        poll_responses=[
            {"status": "queued", "request_id": request_id},
            {"status": "queued", "request_id": request_id},
            {"status": "queued", "request_id": request_id},
        ],
    )

    client._http.post = server.post
    client._http.get = server.get

    def mock_poll_until_done(*, initial, poll_fn, config, logger):
        raise PollTimeoutError("timeout", request_id=request_id)

    monkeypatch.setattr(
        "vaultkit.client.poll_until_done",
        mock_poll_until_done,
    )

    with pytest.raises(PollTimeoutError):
        client.execute(dataset="users")


def test_full_flow_immediate_grant_no_poll(client):
    grant_ref = "grant_123"

    server = MockVaultKitServer(
        intent_response={
            "status": "granted",
            "request_id": "req_1",
            "grant_ref": grant_ref,
        },
        fetch_response={
            "rows": [{"id": 2}],
            "meta": {},
            "correlation_id": "corr_2",
        },
    )

    client._http.post = server.post
    client._http.get = server.get

    result = client.execute(dataset="users")

    assert result.rows == [{"id": 2}]
    assert result.row_count == 1


def test_full_flow_direct_data_no_grant(client):
    server = MockVaultKitServer(
        intent_response={
            "status": "granted",
            "request_id": "req_1",
            "rows": [{"id": 99}],
            "meta": {},
            "correlation_id": "corr_99",
        }
    )

    client._http.post = server.post
    client._http.get = server.get

    result = client.execute(dataset="users")

    assert result.rows == [{"id": 99}]
    assert result.row_count == 1
