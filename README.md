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

## Analytical Queries

Aggregate, group, filter on aggregates and sort within a single dataset:

```python
result = client.execute(
    dataset="orders",
    fields=["region"],
    aggregates=[{"func": "sum", "field": "amount", "alias": "total"}],
    having=[{"field": "SUM(amount)", "operator": "gt", "value": 1000}],
    order_by={"column": "total", "direction": "desc"},
    limit=10,
    purpose="Quarterly revenue by region",
)
# [{"region": "US", "total": 18250}, {"region": "CA", "total": 4100}, ...]
```

- `aggregates`: `func` is one of `count`, `sum`, `avg`, `min`, `max`; use `field="*"` with `count`.
- `group_by`: optional. Defaults to `fields`; if given, it must include every entry in `fields`.
  An entry can also be a time bucket of a timestamp or date field, which groups by period
  (`day`, `week`, `month`, `quarter` or `year`; `alias` and `timezone` are optional, and
  the time zone defaults to UTC). Use one bucketed query for a trend instead of one query
  per period:

  ```python
  client.execute(
      dataset="payments",
      aggregates=[{"func": "count", "field": "*", "alias": "failures"}],
      filters=[{"field": "status", "operator": "eq", "value": "failed"}],
      group_by=[{"field": "created_at", "bucket": "quarter", "alias": "quarter"}],
      order_by={"column": "quarter"},
      purpose="Failed payments per quarter",
  )
  ```

  Bucketing a fully or partially masked field is denied, like grouping by it. Needs a
  control plane with time buckets (vaultkit#106); older ones reject the request.
- `having`: needs an aggregate expression such as `SUM(amount)`, not an alias.
- `order_by`: a field, an aggregate alias or an aggregate expression, `asc` (default) or `desc`.
- `fields` can be omitted for a single total, e.g. `aggregates=[{"func": "count", "field": "*"}]`.

Policies apply to every field these clauses use. `min`/`max`/`sum`/`avg` over a masked
field are denied; `count` is allowed. Joins are not supported.

> Requires a VaultKit control plane with intent analytics support. Older control
> planes ignore these parameters and return ungrouped rows.

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

The tools, also served by the MCP server (`vaultkit-mcp`):

| Tool | What it does |
|---|---|
| `vaultkit_discover` | Lists the datasets the agent can query, with each one's access level. |
| `vaultkit_describe` | Lists a dataset's fields and types, and what a query for each would get: allowed, masked, or needing approval (and from whom). |
| `vaultkit_query` | Queries one dataset. |
| `vaultkit_check_approval` | Checks a request that's waiting for approval, and returns its rows once approved. |

Every tool description tells the agent to call `vaultkit_describe` before querying a
dataset it hasn't described, and never to guess field names. A request with an unknown
field comes back as `{"status": "validation_error", "error": "Unknown field `brand` on
`payment_methods`. Valid fields: …"}`, with the server's message as it is, and isn't
retried.

When VaultKit is busy (`429`, or `503` with `Retry-After`), the SDK waits as long as
`Retry-After` says, backing off if it stays busy. After a few attempts
(`RetryConfig.max_attempts`, default 3) it raises `BusyError`: "VaultKit is busy. Try again
later." Tools return it as `{"status": "busy", ...}`. A `Retry-After` longer than
`RetryConfig.max_retry_after_s` (default 30 s) raises `BusyError` at once instead of
blocking.

Field lists are no longer put in `vaultkit_query`'s description. To get them back, pass
`fetch_schema_hints=True` to `ToolBuilder.build`, or set `VAULTKIT_MCP_SCHEMA_HINTS=1`
for the MCP server. Either way, every dataset's schema is fetched when the tools are
built. `VAULTKIT_MCP_INCLUDE_DESCRIBE=0` leaves `vaultkit_describe` out.

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