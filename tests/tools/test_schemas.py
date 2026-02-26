import pytest

from vaultkit.tools.schemas import (
    discover_tool_schema,
    query_tool_schema,
    check_approval_tool_schema,
)


def test_discover_tool_schema_basic():
    tool = discover_tool_schema(dataset_names=["users"])

    assert "function" in tool
    assert tool["function"]["name"] == "vaultkit_discover"


def test_query_tool_schema_basic():
    tool = query_tool_schema(
        dataset_names=["users"],
        schema_hints={"users": ["id", "email"]},
    )

    assert "function" in tool
    assert tool["function"]["name"] == "vaultkit_query"


def test_check_approval_tool_schema_basic():
    tool = check_approval_tool_schema()

    assert "function" in tool
    assert tool["function"]["name"] == "vaultkit_check_approval"


def test_query_tool_schema_passes_dataset_names():
    tool = query_tool_schema(dataset_names=["users"])

    schema = tool["function"]["parameters"]

    # We don’t assert full structure, just that dataset shows up somewhere
    assert "users" in str(schema)


def test_query_tool_schema_passes_schema_hints():
    tool = query_tool_schema(
        dataset_names=["users"],
        schema_hints={"users": ["email (masked)"]},
    )

    schema = tool["function"]["parameters"]

    assert "email" in str(schema)
