import pytest
import httpx

from vaultkit.core.http import HttpClient
from vaultkit.errors.exceptions import DeniedError, ForbiddenError, TransportError


class DummyResponse:
    def __init__(self, status_code=200, json_data=None, text="", headers=None):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
        self.headers = headers or {}
        self.content = b"1" if json_data is not None else b""

    def json(self):
        if isinstance(self._json_data, Exception):
            raise self._json_data
        return self._json_data


@pytest.fixture
def client(monkeypatch):
    client = HttpClient(base_url="http://test", token="token")

    def mock_request(method, url, headers=None, params=None, json=None):
        return DummyResponse(json_data={"ok": True})

    monkeypatch.setattr(client._client, "request", mock_request)

    return client


def test_get_success(client):
    res = client.get("/test")

    assert res == {"ok": True}


def test_post_success(client):
    res = client.post("/test", json_body={"a": 1})

    assert res == {"ok": True}


def test_empty_response_returns_empty_dict(monkeypatch):
    client = HttpClient(base_url="http://test", token="token")

    def mock_request(*args, **kwargs):
        r = DummyResponse(status_code=200)
        r.content = b""
        return r

    monkeypatch.setattr(client._client, "request", mock_request)

    res = client.get("/test")

    assert res == {}


def test_non_dict_json_wrapped(monkeypatch):
    client = HttpClient(base_url="http://test", token="token")

    def mock_request(*args, **kwargs):
        return DummyResponse(json_data=[1, 2, 3])

    monkeypatch.setattr(client._client, "request", mock_request)

    res = client.get("/test")

    assert res == {"data": [1, 2, 3]}


def test_invalid_json_raises_transport_error(monkeypatch):
    client = HttpClient(base_url="http://test", token="token")

    def mock_request(*args, **kwargs):
        return DummyResponse(json_data=ValueError("bad json"))

    monkeypatch.setattr(client._client, "request", mock_request)

    with pytest.raises(TransportError):
        client.get("/test")


def test_http_error_maps(monkeypatch):
    client = HttpClient(base_url="http://test", token="token")

    def mock_request(*args, **kwargs):
        return DummyResponse(
            status_code=422,
            json_data={"message": "error"},
        )

    monkeypatch.setattr(client._client, "request", mock_request)

    with pytest.raises(Exception):  # map_http_error result
        client.get("/test")


def test_network_error_raises_transport_error(monkeypatch):
    client = HttpClient(base_url="http://test", token="token")

    def mock_request(*args, **kwargs):
        raise httpx.RequestError("network down")

    monkeypatch.setattr(client._client, "request", mock_request)

    with pytest.raises(TransportError):
        client.get("/test")


def test_retry_fn_used(monkeypatch):
    called = {"retry": False}

    def retry_fn(fn):
        called["retry"] = True
        return fn()

    client = HttpClient(
        base_url="http://test",
        token="token",
        retry_fn=retry_fn,
    )

    def mock_request(*args, **kwargs):
        return DummyResponse(json_data={"ok": True})

    monkeypatch.setattr(client._client, "request", mock_request)

    client.get("/test")

    assert called["retry"] is True


def _client_returning(monkeypatch, status_code, body):
    client = HttpClient(base_url="http://test", token="token")

    def mock_request(*args, **kwargs):
        return DummyResponse(status_code=status_code, json_data=body)

    monkeypatch.setattr(client._client, "request", mock_request)
    return client


def test_intent_denial_raises_denied_error_with_reason(monkeypatch):
    # Shape the control plane's intent API sends for a policy denial.
    client = _client_returning(monkeypatch, 403, {
        "status": "denied",
        "policy_id": "deny_pii",
        "reason": "PII access is not allowed for this purpose",
    })

    with pytest.raises(DeniedError) as exc_info:
        client.post("/intent/requests", json_body={})

    err = exc_info.value
    assert err.policy_id == "deny_pii"
    assert err.reason == "PII access is not allowed for this purpose"
    assert err.message == "PII access is not allowed for this purpose"


def test_legacy_policy_denied_type_still_raises_denied_error(monkeypatch):
    client = _client_returning(monkeypatch, 403, {
        "type": "policy_denied",
        "policy_id": "p1",
        "error": "blocked",
    })

    with pytest.raises(DeniedError) as exc_info:
        client.post("/intent/requests", json_body={})

    assert exc_info.value.policy_id == "p1"
    assert exc_info.value.reason == "blocked"


def test_other_403_stays_forbidden(monkeypatch):
    client = _client_returning(monkeypatch, 403, {"error": "token lacks scope"})

    with pytest.raises(ForbiddenError) as exc_info:
        client.get("/test")

    assert not isinstance(exc_info.value, DeniedError)
    assert exc_info.value.message == "token lacks scope"
