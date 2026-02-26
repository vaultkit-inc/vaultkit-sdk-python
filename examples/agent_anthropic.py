"""
Full Anthropic tool-calling agent example.
Production-grade integration pattern for VaultKit + Claude.
"""

import json
import os

import anthropic

from vaultkit import VaultKitClient
from vaultkit.tools import ToolBuilder, ToolExecutor, ToolProvider

# Setup

client = VaultKitClient(
    base_url=os.environ["VAULTKIT_URL"],
    token=os.environ["VAULTKIT_TOKEN"],
    org=os.environ["VAULTKIT_ORG"],
)

anthropic_client = anthropic.Anthropic(
    api_key=os.environ["ANTHROPIC_API_KEY"]
)

# Build tools once (important — includes registry fetch)
tools = ToolBuilder(client).build(
    provider=ToolProvider.ANTHROPIC,
    environment="production",
    include_check_approval=True,
)

executor = ToolExecutor(
    client,
    default_purpose="AI agent analysis",
    default_requester_region="US",
)

SYSTEM_PROMPT = """You are a data analyst agent using VaultKit.

Rules:
- Always include a clear 'purpose' when calling vaultkit_query.
- Only use datasets returned by vaultkit_discover.
- Only use fields that exist in the dataset schema.
- If unsure, call vaultkit_discover first.
- If a query returns pending_approval, inform the user and suggest checking status.
- Do not invent datasets, fields, or filters.
"""

MAX_STEPS = 10


# Agent Loop
def run_agent(user_message: str) -> str:
    messages = [
        {
            "role": "user",
            "content": user_message,
        }
    ]

    for step in range(MAX_STEPS):
        print(f"\n[STEP {step + 1}]")

        response = anthropic_client.messages.create(
            model="claude-3-5-sonnet-latest",
            system=SYSTEM_PROMPT,
            messages=messages,
            tools=tools,
            max_tokens=1024,
        )

        # Claude returns a list of content blocks
        content_blocks = response.content

        tool_calls = []
        final_text_parts = []

        for block in content_blocks:
            if block.type == "tool_use":
                tool_calls.append(block)
            elif block.type == "text":
                final_text_parts.append(block.text)

        # If no tool calls → final answer
        if not tool_calls:
            print("[LLM] final answer")
            return "\n".join(final_text_parts).strip()

        for tool_call in tool_calls:
            tool_name = tool_call.name
            args = tool_call.input or {}

            print(f"[LLM] tool_call → {tool_name} {args}")

            result = executor.execute(tool_name, args)

            print(f"[TOOL] result → {result}")

            # Append tool result in Claude format
            messages.append({
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": tool_call.id,
                        "name": tool_name,
                        "input": args,
                    }
                ],
            })

            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_call.id,
                        "content": json.dumps(result),
                    }
                ],
            })

    return "Agent stopped after reaching max steps."


# Run
if __name__ == "__main__":
    print(run_agent(
        "How many US customers have revenue over $10,000? "
        "Break it down by region if possible."
    ))
