import pytest

from vaultkit.models.dataset_info import DatasetInfo


def test_from_dict_with_name():
    data = {
        "name": "users",
        "datasource": "postgres",
        "visibility": "public",
        "correlation_id": "c1",
    }

    result = DatasetInfo.from_dict(data)

    assert result.dataset == "users"
    assert result.datasource == "postgres"
    assert result.visibility == "public"
    assert result.correlation_id == "c1"


def test_from_dict_with_dataset_key():
    data = {
        "dataset": "orders",
        "datasource": "snowflake",
    }

    result = DatasetInfo.from_dict(data)

    assert result.dataset == "orders"
    assert result.datasource == "snowflake"


def test_name_takes_precedence_over_dataset():
    data = {
        "name": "users",
        "dataset": "ignored",
        "datasource": "postgres",
    }

    result = DatasetInfo.from_dict(data)

    assert result.dataset == "users"


def test_missing_required_fields_raises():
    with pytest.raises(ValueError):
        DatasetInfo.from_dict({})

    with pytest.raises(ValueError):
        DatasetInfo.from_dict({"name": "users"})

    with pytest.raises(ValueError):
        DatasetInfo.from_dict({"datasource": "postgres"})
