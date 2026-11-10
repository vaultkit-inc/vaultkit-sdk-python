import pytest

from vaultkit.tools.definitions import (
    DESCRIBE_FIRST,
    describe_tool_def,
    discover_tool_def,
    query_tool_def,
    check_approval_tool_def,
)


def test_discover_tool_def_basic_structure():
    tool = discover_tool_def()

    assert tool["name"] == "vaultkit_discover"
    assert "description" in tool
    assert "input_schema" in tool

    schema = tool["input_schema"]
    assert schema["type"] == "object"
    assert "properties" in schema


def test_discover_tool_def_includes_dataset_names_in_description():
    tool = discover_tool_def(dataset_names=["users", "orders"])

    description = tool["description"]

    assert "users" in description
    assert "orders" in description


def test_query_tool_def_basic_structure():
    tool = query_tool_def()

    assert tool["name"] == "vaultkit_query"
    assert "description" in tool
    assert "input_schema" in tool

    schema = tool["input_schema"]
    assert schema["type"] == "object"
    assert "properties" in schema


def test_query_tool_def_requires_dataset():
    tool = query_tool_def()

    required = tool["input_schema"]["required"]

    assert "dataset" in required


def test_query_tool_def_with_dataset_names_sets_enum():
    tool = query_tool_def(dataset_names=["users", "orders"])

    dataset_prop = tool["input_schema"]["properties"]["dataset"]

    assert dataset_prop["type"] == "string"
    assert dataset_prop["enum"] == ["users", "orders"]


def test_query_tool_def_without_dataset_names_has_no_enum():
    tool = query_tool_def()

    dataset_prop = tool["input_schema"]["properties"]["dataset"]

    assert "enum" not in dataset_prop


def test_query_tool_def_includes_schema_hints_in_description():
    tool = query_tool_def(
        dataset_names=["users"],
        schema_hints={"users": ["id", "email", "name"]},
    )

    fields_desc = tool["input_schema"]["properties"]["fields"]["description"]

    assert "users" in fields_desc
    assert "email" in fields_desc


def test_query_tool_def_filter_structure_exists():
    tool = query_tool_def()

    filters = tool["input_schema"]["properties"]["filters"]

    assert filters["type"] == "array"
    assert "items" in filters


def test_query_tool_def_limit_constraints():
    tool = query_tool_def()

    limit = tool["input_schema"]["properties"]["limit"]

    assert limit["type"] == "integer"
    assert limit["minimum"] == 1
    assert limit["maximum"] == 10000


def test_check_approval_tool_def_structure():
    tool = check_approval_tool_def()

    assert tool["name"] == "vaultkit_check_approval"
    assert "description" in tool
    assert "input_schema" in tool

    schema = tool["input_schema"]

    assert schema["type"] == "object"
    assert "request_id" in schema["properties"]
    assert "request_id" in schema["required"]


def test_query_tool_def_advertises_analytics():
    props = query_tool_def()["input_schema"]["properties"]

    aggregates = props["aggregates"]
    assert aggregates["type"] == "array"
    assert aggregates["items"]["properties"]["func"]["enum"] == ["count", "sum", "avg", "min", "max"]
    assert aggregates["items"]["required"] == ["func", "field"]

    group_by = props["group_by"]["items"]["oneOf"]
    assert group_by[0] == {"type": "string"}
    assert group_by[1]["properties"]["bucket"]["enum"] == ["day", "week", "month", "quarter", "year"]
    assert group_by[1]["required"] == ["field", "bucket"]

    having = props["having"]["items"]
    assert having["properties"]["operator"]["enum"] == ["gt", "lt", "eq", "gte", "lte"]
    assert having["required"] == ["field", "operator", "value"]

    order_by = props["order_by"]
    assert order_by["properties"]["direction"]["enum"] == ["asc", "desc"]
    assert order_by["required"] == ["column"]


def test_query_tool_def_keeps_dataset_as_the_only_required_input():
    assert query_tool_def()["input_schema"]["required"] == ["dataset"]


def test_query_tool_def_says_joins_are_not_supported():
    assert "joins are not supported" in query_tool_def()["description"]


def test_query_tool_def_steers_trends_to_one_bucketed_query():
    tool = query_tool_def()

    assert "ONE query that groups by a time bucket" in tool["description"]
    example = tool["input_schema"]["properties"]["group_by"]["description"]
    assert "{field: 'created_at', bucket: 'quarter', alias: 'quarter'}" in example


def test_describe_tool_def_structure():
    tool = describe_tool_def(dataset_names=["payment_methods", "plans"])

    assert tool["name"] == "vaultkit_describe"
    assert tool["input_schema"]["required"] == ["dataset"]
    assert tool["input_schema"]["properties"]["dataset"]["enum"] == ["payment_methods", "plans"]
    assert "approval" in tool["description"]


def test_every_data_tool_says_to_describe_first_and_never_guess():
    for tool in (discover_tool_def(), describe_tool_def(), query_tool_def()):
        assert DESCRIBE_FIRST in tool["description"]
    assert DESCRIBE_FIRST == (
        "Call vaultkit_describe before querying a dataset you haven't described. Never guess field names."
    )


def test_query_tool_def_lists_no_fields_unless_given_hints():
    fields_desc = query_tool_def(dataset_names=["users"])["input_schema"]["properties"]["fields"]["description"]

    assert "VALID FIELDS" not in fields_desc
    assert "vaultkit_describe" in fields_desc


def test_query_tool_def_lists_hints_for_every_dataset():
    hints = {f"ds{i}": ["id"] for i in range(8)}

    fields_desc = query_tool_def(schema_hints=hints)["input_schema"]["properties"]["fields"]["description"]

    assert all(f"ds{i}: id" in fields_desc for i in range(8))
