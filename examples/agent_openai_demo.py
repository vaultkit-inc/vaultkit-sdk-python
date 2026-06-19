"""
VaultKit AI Agent Demo
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

OUTPUT FORMAT:
- ALWAYS present data results as a markdown table

GOAL:
Safely retrieve and analyze governed data.
"""

MAX_STEPS = 10


def format_result(result: dict) -> None:
    status = result.get("status")

    if status in ("ok", "approved"):
        rows = result.get("data") or result.get("rows", [])
        masked = result.get("masked_fields", [])
        print(f"\n  ✅ {len(rows)} row(s) retrieved", end="")
        print()

    elif status == "denied":
        print(f"\n  🚫 Access denied — {result.get('reason', 'Policy violation')}")

    elif status == "error":
        print(f"\n  ⚠️  {result.get('message', 'Unknown error')}")


def format_tool_call(name: str, args: dict) -> None:
    if name == "vaultkit_discover":
        print(f"\n  🔍 Discovering datasets...")
    elif name == "vaultkit_query":
        dataset = args.get("dataset", "unknown")
        print(f"\n  📋 Querying {dataset}...")


def run_agent(user_message: str) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    print("\n" + "─" * 60)
    print("  VaultKit Agent")
    print("─" * 60)

    for step in range(MAX_STEPS):

        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=tools,
            tool_choice="auto",
        )

        msg = response.choices[0].message
        messages.append(msg.model_dump())

        if not msg.tool_calls:
            print("\n" + "─" * 60)
            print("  Agent Response")
            print("─" * 60)
            print(f"\n{msg.content}")
            print()
            return msg.content or ""

        for tool_call in msg.tool_calls:
            try:
                args = json.loads(tool_call.function.arguments)
            except Exception:
                args = {}

            format_tool_call(tool_call.function.name, args)

            result = executor.execute(tool_call.function.name, args)

            format_result(result)

            if result.get("status") == "pending_approval":
                request_id = result.get("request_id")

                print(f"\n  ⏳ Waiting for human approval...")
                print(f"  Run: vkit approval:approve {request_id}")

                max_wait = 120
                interval = 5
                elapsed = 0

                while elapsed < max_wait:
                    time.sleep(interval)
                    elapsed += interval

                    check = executor.execute(
                        "vaultkit_check_approval",
                        {"request_id": request_id},
                    )

                    if check.get("status") in ("approved", "denied"):
                        format_result(check)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "content": json.dumps(check),
                        })
                        break
                else:
                    timeout_msg = {
                        "status": "error",
                        "message": "Approval timed out after 2 minutes.",
                    }
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(timeout_msg),
                    })

                continue

            if result.get("status") == "error":
                continue

            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result),
            })

    return "  Agent stopped after max steps."


if __name__ == "__main__":
    print("\n  VaultKit — Runtime Governance for AI Agents")
    print("  docs.vaultkit.io\n")

    while True:
        question = input("Ask the agent (or 'quit' to exit): ")
        if question.lower() == "quit":
            break
        run_agent(question)
