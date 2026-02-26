from types import SimpleNamespace

import pytest

from vaultkit.tools.builder import ToolBuilder
from vaultkit.tools.adapters import ToolProvider


class MockClient:
    def datasets(self, *, environment=None, requester_region=None):
        return [
            SimpleNamespace(dataset="users", datasource="postgres"),
            SimpleNamespace(dataset="orders", datasource="snowflake"),
        ]

    def schema(self, dataset, *, environment=None, requester_region=None):
        if dataset == "users":
            return SimpleNamespace(
                field_summaries=["id", "email", "created_at"],
                field_names=["id", "email", "created_at"],
            )
        if dataset == "orders":
            return SimpleNamespace(
                field_summaries=["id", "amount", "status"],
                field_names=["id", "amount", "status"],
            )
        raise Exception("unknown dataset")


def test_build_raw_with_schema_hints():
    builder = ToolBuilder(MockClient())

    tools = builder.build(provider=ToolProvider.RAW)

    assert len(tools) >= 2

    query_tool = next(t for t in tools if t["name"] == "vaultkit_query")

    props = query_tool["input_schema"]["properties"]

    # dataset enum should be present
    assert "dataset" in props
    assert props["dataset"]["enum"] == ["users", "orders"]

    # fields description should include hints
    fields_desc = props["fields"]["description"]
    assert "users:" in fields_desc
    assert "orders:" in fields_desc


def test_build_openai_format():
    builder = ToolBuilder(MockClient())

    tools = builder.build(provider=ToolProvider.OPENAI)

    assert all(t["type"] == "function" for t in tools)

    names = [t["function"]["name"] for t in tools]
    assert "vaultkit_query" in names
    assert "vaultkit_discover" in names


def test_build_anthropic_format():
    builder = ToolBuilder(MockClient())

    tools = builder.build(provider=ToolProvider.ANTHROPIC)

    names = [t["name"] for t in tools]

    assert "vaultkit_query" in names
    assert "vaultkit_discover" in names

    for t in tools:
        assert "input_schema" in t


def test_build_without_schema_hints():
    builder = ToolBuilder(MockClient())

    tools = builder.build(
        provider=ToolProvider.RAW,
        fetch_schema_hints=False,
    )

    query_tool = next(t for t in tools if t["name"] == "vaultkit_query")

    fields_desc = query_tool["input_schema"]["properties"]["fields"]["description"]

    # Should not include example hints
    assert "Example fields" not in fields_desc


def test_build_with_explicit_datasets():
    builder = ToolBuilder(MockClient())

    tools = builder.build(
        provider=ToolProvider.RAW,
        datasets=["custom_ds"],
        fetch_schema_hints=False,
    )

    query_tool = next(t for t in tools if t["name"] == "vaultkit_query")

    enum = query_tool["input_schema"]["properties"]["dataset"]["enum"]

    assert enum == ["custom_ds"]


def test_dataset_fetch_failure_returns_empty():
    class FailingClient:
        def datasets(self, **kwargs):
            raise Exception("boom")

    builder = ToolBuilder(FailingClient())

    tools = builder.build(provider=ToolProvider.RAW)

    query_tool = next(t for t in tools if t["name"] == "vaultkit_query")

    # no enum restriction if datasets failed
    dataset_prop = query_tool["input_schema"]["properties"]["dataset"]
    assert "enum" not in dataset_prop


def test_schema_fetch_failure_skips_hints():
    class PartialClient(MockClient):
        def schema(self, dataset, **kwargs):
            raise Exception("fail schema")

    builder = ToolBuilder(PartialClient())

    tools = builder.build(provider=ToolProvider.RAW)

    query_tool = next(t for t in tools if t["name"] == "vaultkit_query")

    fields_desc = query_tool["input_schema"]["properties"]["fields"]["description"]

    assert "Example fields" not in fields_desc


def test_build_minimal():
    builder = ToolBuilder(MockClient())

    tools = builder.build_minimal(provider=ToolProvider.RAW)

    assert len(tools) == 1
    assert tools[0]["name"] == "vaultkit_query"
