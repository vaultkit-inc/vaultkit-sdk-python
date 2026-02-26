"""
VaultKit AI Agent Demo (Production)

This version is optimized for:
- demos
- real-world agent behavior

Key upgrades:
- no exception leakage from executor
- approval flow handling
- clearer logs
- discover-first bias
- resilient loop
"""

import json
import os
import time

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


SYSTEM_PROMPT = """You are a production-grade data analyst agent using VaultKit.

STRICT RULES:
- ALWAYS call vaultkit_discover first before querying
- ONLY use datasets returned by discover
- ONLY use valid fields from schema
- ALWAYS include a clear 'purpose' when querying
- NEVER invent datasets or fields
- If approval is required, explain clearly and guide the user

GOAL:
Safely retrieve and analyze governed data.
"""


MAX_STEPS = 10


# Agent Loop

def run_agent(user_message: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    print("\n Starting VaultKit Agent\n")

    for step in range(MAX_STEPS):
        print(f"\n STEP {step + 1}")

        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )

        msg = response.choices[0].message
        messages.append(msg.model_dump())

        # Final answer
        if not msg.tool_calls:
            print("\n FINAL ANSWER\n")
            print(msg.content)
            return msg.content or ""

        for tool_call in msg.tool_calls:
            try:
                args = json.loads(tool_call.function.arguments)
            except Exception:
                args = {}

            print(f" TOOL CALL → {tool_call.function.name}")
            print(f" ARGS      → {args}")

            result = executor.execute(tool_call.function.name, args)

            print(f" RESULT    → {result}")

            # Approval flow (key differentiator)
            if result.get("status") == "pending_approval":
                request_id = result.get("request_id")

                print("\n Approval required. Simulating wait...\n")
                time.sleep(2)

                check = executor.execute(
                    "vaultkit_check_approval",
                    {"request_id": request_id},
                )

                print(f" APPROVAL CHECK → {check}")

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(check),
                })

                continue

            # Retry simple transient errors
            if result.get("status") == "error":
                print("⚠️  Retrying step...")
                continue

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result),
            })

    return "⚠️ Agent stopped after max steps."


# Run

if __name__ == "__main__":
    print(
        run_agent(
            "Find users signup source in the last 7 days and summarize activity trends"
        )
    )
