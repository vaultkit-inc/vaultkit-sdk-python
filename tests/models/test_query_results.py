import pytest

from vaultkit.models.query_result import QueryResult


def test_from_dict_success():
    data = {
        "status": "GRANTED",
        "request_id": "req_1",
        "grant_ref": "g1",
        "rows": [{"id": 1}],
    }

    result = QueryResult.from_dict(data)

    assert result.status == "granted"
    assert result.request_id == "req_1"
    assert result.grant_ref == "g1"
    assert result.rows == [{"id": 1}]


def test_status_normalization():
    result = QueryResult.from_dict({
        "status": "  GRANTED  ",
        "request_id": "req_1",
    })

    assert result.status == "granted"


def test_missing_status_raises():
    with pytest.raises(ValueError):
        QueryResult.from_dict({})


def test_missing_request_id_for_required_status_raises():
    with pytest.raises(ValueError):
        QueryResult.from_dict({
            "status": "queued",
        })


def test_grant_id_alias():
    result = QueryResult.from_dict({
        "status": "granted",
        "request_id": "req_1",
        "grant_id": "g123",
    })

    assert result.grant_ref == "g123"


def test_rows_and_masked_fields_defaults():
    result = QueryResult.from_dict({
        "status": "granted",
        "request_id": "req_1",
    })

    assert result.rows == []
    assert result.masked_fields == []


def test_properties_granted():
    result = QueryResult.from_dict({
        "status": "granted",
        "request_id": "req_1",
    })

    assert result.is_granted is True
    assert result.is_denied is False
    assert result.is_terminal is True
    assert result.needs_approval is False


def test_properties_denied():
    result = QueryResult.from_dict({
        "status": "denied",
    })

    assert result.is_denied is True
    assert result.is_terminal is True


def test_properties_pending():
    result = QueryResult.from_dict({
        "status": "queued",
        "request_id": "req_1",
    })

    assert result.is_pending is True
    assert result.needs_approval is True
    assert result.is_terminal is False


def test_has_data():
    result = QueryResult.from_dict({
        "status": "granted",
        "request_id": "req_1",
        "rows": [{"id": 1}],
    })

    assert result.has_data is True

    empty = QueryResult.from_dict({
        "status": "granted",
        "request_id": "req_1",
    })

    assert empty.has_data is False
