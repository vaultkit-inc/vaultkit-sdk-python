import pytest

from vaultkit.models.fetch_result import FetchResult


def test_from_dict_success():
    data = {
        "rows": [{"id": 1}],
        "meta": {"foo": "bar"},
        "correlation_id": "corr_1",
    }

    result = FetchResult.from_dict(data)

    assert result.rows == [{"id": 1}]
    assert result.meta == {"foo": "bar"}
    assert result.correlation_id == "corr_1"


def test_from_dict_defaults():
    result = FetchResult.from_dict({})

    assert result.rows == []
    assert result.meta is None
    assert result.correlation_id is None


def test_from_dict_invalid_rows_sanitized():
    result = FetchResult.from_dict({
        "rows": "not-a-list"
    })

    assert result.rows == []


def test_from_dict_invalid_meta_sanitized():
    result = FetchResult.from_dict({
        "meta": "not-a-dict"
    })

    assert result.meta is None


def test_data_alias():
    result = FetchResult.from_dict({
        "rows": [{"id": 1}]
    })

    assert result.data == [{"id": 1}]


def test_row_count():
    result = FetchResult.from_dict({
        "rows": [{"id": 1}, {"id": 2}]
    })

    assert result.row_count == 2


def test_masked_fields_present():
    result = FetchResult.from_dict({
        "rows": [],
        "meta": {"masked_fields": ["email", "ssn"]}
    })

    assert result.masked_fields == ["email", "ssn"]


def test_masked_fields_missing():
    result = FetchResult.from_dict({
        "rows": [],
        "meta": {}
    })

    assert result.masked_fields == []


def test_masked_fields_invalid():
    result = FetchResult.from_dict({
        "rows": [],
        "meta": {"masked_fields": "not-a-list"}
    })

    assert result.masked_fields == []


def test_is_empty_true():
    result = FetchResult.from_dict({})

    assert result.is_empty is True


def test_is_empty_false():
    result = FetchResult.from_dict({
        "rows": [{"id": 1}]
    })

    assert result.is_empty is False
