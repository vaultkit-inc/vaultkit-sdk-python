# VaultKit Python SDK

> Secure, policy-driven data access for AI agents and applications.

VaultKit is a control plane for governed data access. This SDK allows Python applications and AI agents to safely query data with built-in policy enforcement, approval workflows, and auditability.

---

## Features

- Policy-enforced data access (masking, approval, deny)
- First-class support for AI agents (OpenAI, Anthropic)
- Built-in approval workflows
- Automatic polling and retries
- Schema-aware dataset discovery
- Simple, high-level API via `execute()`

---

## Installation

```bash
pip install vaultkit
```

---

## Quick Start

```python
from vaultkit import VaultKitClient

client = VaultKitClient(
    base_url="http://localhost:3000",
    token="YOUR_TOKEN",
    org="YOUR_ORG",
)

result = client.execute(
    dataset="users",
    fields=["id", "email"],
    limit=10,
    purpose="Analyze user activity",
)

print(result.rows)
```

---

## AI Agent Usage

VaultKit provides built-in tools for LLM agents.

```python
from vaultkit.tools import ToolBuilder, ToolExecutor, ToolProvider

builder = ToolBuilder(client)

tools = builder.build(
    provider=ToolProvider.OPENAI,
    include_check_approval=True,
)

executor = ToolExecutor(client)

result = executor.execute(
    "vaultkit_query",
    {
        "dataset": "users",
        "limit": 5,
        "purpose": "Analyze user trends",
    },
)
```

See full example: [`examples/agent_openai_demo.py`](examples/agent_openai_demo.py)

---

## Approval Flow

Some queries require human approval before data is returned.

```python
from vaultkit.errors.exceptions import ApprovalRequiredError

try:
    client.execute(dataset="sensitive_data", purpose="Analysis")
except ApprovalRequiredError as e:
    print(f"Approval required. Request ID: {e.request_id}")
```

Once approved, resume with:

```python
result = client.poll_request(request_id="req_123")
```

---

## API Overview

### High-Level

| Method | Description |
|---|---|
| `client.execute(...)` | Full lifecycle: query → poll → fetch. Recommended for most use cases. |

### Low-Level

| Method | Description |
|---|---|
| `client.query(...)` | Submit an intent request, get a `QueryResult` |
| `client.poll(result)` | Block until a queued result reaches a terminal state |
| `client.fetch(grant_ref=...)` | Redeem a grant for data |
| `client.poll_request(request_id=...)` | Poll by request ID (used in approval flows) |

### Discovery

| Method | Description |
|---|---|
| `client.datasets()` | List authorized datasets from the registry |
| `client.schema("users")` | Get field-level schema for a dataset |

---

## How It Works

```
Client → VaultKit → Policy Engine → Data Source
                         ↓
                  Enforced Policies
```

1. Queries are evaluated against policy bundles at runtime
2. Sensitive fields may be masked based on requester context
3. Some datasets require human approval before access is granted
4. All access is logged and auditable

---

## Why VaultKit?

Traditional access control is static — permissions are set upfront and rarely change. VaultKit enables:

- **Runtime, policy-driven access** — decisions made at query time based on context
- **AI-safe data access** — purpose and clearance are first-class query parameters
- **Auditability and compliance** — every request is tracked with correlation IDs

---

## Environment Variables

```bash
export VAULTKIT_URL=http://localhost:3000
export VAULTKIT_TOKEN=your_token
export VAULTKIT_ORG=your_org
```

Or use a `.env` file (see [`.env.example`](.env.example)).

---

## Local Development

Start VaultKit locally with Docker:

```bash
docker compose up
```

Run the test suite:

```bash
pytest
```

---

## License

MIT