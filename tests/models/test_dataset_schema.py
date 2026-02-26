import pytest

from vaultkit.models.dataset_schema import DatasetSchema


def test_from_dict_success():
    data = {
        "dataset": "users",
        "datasource": "postgres",
        "fields": [{"name": "id"}],
        "correlation_id": "c1",
    }

    schema = DatasetSchema.from_dict(data)

    assert schema.dataset == "users"
    assert schema.datasource == "postgres"
    assert schema.fields == [{"name": "id"}]
    assert schema.correlation_id == "c1"


def test_from_dict_missing_required_fields():
    with pytest.raises(ValueError):
        DatasetSchema.from_dict({})


def test_from_dict_invalid_fields_defaults_to_empty():
    schema = DatasetSchema.from_dict({
        "dataset": "users",
        "datasource": "postgres",
        "fields": "invalid",
    })

    assert schema.fields == []


def test_field_names():
    schema = DatasetSchema.from_dict({
        "dataset": "users",
        "datasource": "postgres",
        "fields": [
            {"name": "id"},
            {"name": "email"},
            {"no_name": True},
            "invalid",
        ],
    })

    assert schema.field_names == ["id", "email"]


def test_field_map():
    schema = DatasetSchema.from_dict({
        "dataset": "users",
        "datasource": "postgres",
        "fields": [
            {"name": "id", "type": "int"},
            {"name": "email", "type": "string"},
        ],
    })

    field_map = schema.field_map

    assert field_map["id"]["type"] == "int"
    assert field_map["email"]["type"] == "string"


def test_field_map_ignores_invalid_entries():
    schema = DatasetSchema.from_dict({
        "dataset": "users",
        "datasource": "postgres",
        "fields": [
            {"name": "id"},
            {"no_name": True},
            "invalid",
        ],
    })

    assert "id" in schema.field_map
    assert len(schema.field_map) == 1


def test_field_summaries_basic():
    schema = DatasetSchema.from_dict({
        "dataset": "users",
        "datasource": "postgres",
        "fields": [
            {"name": "email"},
        ],
    })

    assert schema.field_summaries == ["email"]


def test_field_summaries_with_flags():
    schema = DatasetSchema.from_dict({
        "dataset": "users",
        "datasource": "postgres",
        "fields": [
            {
                "name": "email",
                "masked": True,
                "visibility": "deny",
                "sensitivity": "high",
            }
        ],
    })

    summaries = schema.field_summaries

    assert len(summaries) == 1
    assert "email" in summaries[0]
    assert "(masked)" in summaries[0]
    assert "(restricted)" in summaries[0]
    assert "(sensitivity: high)" in summaries[0]


def test_field_summaries_ignores_invalid_entries():
    schema = DatasetSchema.from_dict({
        "dataset": "users",
        "datasource": "postgres",
        "fields": [
            {"name": "id"},
            {"no_name": True},
            "invalid",
        ],
    })

    assert schema.field_summaries == ["id"]
