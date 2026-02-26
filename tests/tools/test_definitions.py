import pytest

from vaultkit.tools.definitions import (
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
