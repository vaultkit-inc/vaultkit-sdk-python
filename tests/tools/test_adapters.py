from vaultkit.tools.adapters.openai import to_openai_tool
from vaultkit.tools.adapters.anthropic import to_anthropic_tool


def make_def():
    return {
        "name": "vaultkit_query",
        "description": "Query data",
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset": {"type": "string"}
            },
            "required": ["dataset"],
        },
    }


# OpenAI

def test_to_openai_tool_mapping():
    tool = to_openai_tool(make_def())

    assert tool["type"] == "function"

    fn = tool["function"]
    assert fn["name"] == "vaultkit_query"
    assert fn["description"] == "Query data"
    assert fn["parameters"]["type"] == "object"
    assert "dataset" in fn["parameters"]["properties"]


def test_to_openai_tool_defaults():
    tool = to_openai_tool({"name": "vaultkit_query"})

    fn = tool["function"]

    assert fn["description"] == ""
    assert fn["parameters"]["type"] == "object"
    assert fn["parameters"]["properties"] == {}


# Anthropic

def test_to_anthropic_tool_mapping():
    tool = to_anthropic_tool(make_def())

    assert tool["name"] == "vaultkit_query"
    assert tool["description"] == "Query data"
    assert tool["input_schema"]["type"] == "object"
    assert "dataset" in tool["input_schema"]["properties"]


def test_to_anthropic_tool_defaults():
    tool = to_anthropic_tool({"name": "vaultkit_query"})

    assert tool["description"] == ""
    assert tool["input_schema"]["type"] == "object"
    assert tool["input_schema"]["properties"] == {}
