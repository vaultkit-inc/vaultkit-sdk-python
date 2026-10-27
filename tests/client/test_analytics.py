import pytest
from unittest.mock import MagicMock

from vaultkit.client import VaultKitClient
from vaultkit.errors.exceptions import ValidationError
from vaultkit.models.fetch_result import FetchResult
from vaultkit.models.query_result import QueryResult


@pytest.fixture
def client():
    c = VaultKitClient(base_url="http://test", token="token", org="org")
    c._http = MagicMock()
    c._http.post.return_value = {"status": "granted", "request_id": "req_1", "grant_ref": "grant_1"}
    return c


ANALYTICS = {
    "aggregates": [{"func": "sum", "field": "amount", "alias": "total"}],
    "group_by": ["region"],
    "having": [{"field": "SUM(amount)", "operator": "gt", "value": 1000}],
    "order_by": {"column": "total", "direction": "desc"},
}


def sent_request(client):
    _, kwargs = client._http.post.call_args
    return kwargs["json_body"]["request"]


def test_query_sends_analytics_inside_the_request(client):
    client.query(dataset="orders", fields=["region"], **ANALYTICS)

    req = sent_request(client)

    assert req["dataset"] == "orders"
    assert req["fields"] == ["region"]
    for key, value in ANALYTICS.items():
        assert req[key] == value


def test_query_omits_analytics_that_are_not_given(client):
    client.query(dataset="orders", fields=["region"])

    req = sent_request(client)

    for key in ANALYTICS:
        assert key not in req


def test_query_allows_aggregates_without_fields(client):
    client.query(dataset="orders", aggregates=[{"func": "count", "field": "*"}])

    req = sent_request(client)

    assert "fields" not in req
    assert req["aggregates"] == [{"func": "count", "field": "*"}]


def test_execute_forwards_analytics_to_query(client):
    client.query = MagicMock(
        return_value=QueryResult.from_dict({"status": "granted", "request_id": "req_1", "grant_ref": "grant_1"})
    )
    client.fetch = MagicMock(return_value=FetchResult.from_dict({"rows": [{"region": "US", "total": 5}], "meta": {}}))

    result = client.execute(dataset="orders", fields=["region"], **ANALYTICS)

    assert result.rows == [{"region": "US", "total": 5}]
    _, kwargs = client.query.call_args
    for key, value in ANALYTICS.items():
        assert kwargs[key] == value


@pytest.mark.parametrize(
    "overrides",
    [
        {"aggregates": {"func": "sum", "field": "amount"}},
        {"aggregates": []},
        {"aggregates": ["sum(amount)"]},
        {"aggregates": [{"func": "sum"}]},
        {"group_by": "region"},
        {"group_by": ["region", ""]},
        {"having": {"field": "SUM(amount)"}},
        {"having": ["SUM(amount) > 1"]},
        {"order_by": "total"},
        {"order_by": {"direction": "desc"}},
    ],
)
def test_query_rejects_malformed_analytics_before_sending(client, overrides):
    with pytest.raises(ValidationError):
        client.query(dataset="orders", fields=["region"], **overrides)

    client._http.post.assert_not_called()
