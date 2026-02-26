"""
Full OpenAI tool-calling agent example.
Production-grade integration pattern for VaultKit + GPT-4o.
"""

import json
import os

import openai

from vaultkit import VaultKitClient
from vaultkit.tools import ToolBuilder, ToolExecutor, ToolProvider

# Setup
client = VaultKitClient(
    base_url=os.environ["VAULTKIT_URL"],
    token=os.environ["VAULTKIT_TOKEN"],
    org=os.environ["VAULTKIT_ORG"],
)

openai_client = openai.OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# Build tools once at the start, then reuse across calls for efficiency (caching, no N+1 registry calls).
tools = ToolBuilder(client).build(
    provider=ToolProvider.OPENAI,
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
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    for step in range(MAX_STEPS):
        print(f"\n[STEP {step + 1}]")

        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )

        msg = response.choices[0].message
        messages.append(msg.model_dump())

        # No tool call → final answer
        if not msg.tool_calls:
            print("[LLM] final answer")
            return msg.content or ""

        for tool_call in msg.tool_calls:
            try:
                args = json.loads(tool_call.function.arguments)
            except Exception:
                args = {}

            print(f"[LLM] tool_call → {tool_call.function.name} {args}")

            from vaultkit.errors.exceptions import ApprovalRequiredError, DeniedError

            try:
                result = executor.execute(tool_call.function.name, args)

            except ApprovalRequiredError as e:
                result = {
                    "status": "pending_approval",
                    "message": str(e),
                    "request_id": e.request_id,
                }

            except DeniedError as e:
                result = {
                    "status": "denied",
                    "message": str(e),
                }

            print(f"[TOOL] result → {result}")

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result),
            })

    return "Agent stopped after reaching max steps."


# Run
if __name__ == "__main__":
    print(run_agent(
        "get details of this request b8c2412b-0f78-41cf-a0af-11846bc80448"
    ))
