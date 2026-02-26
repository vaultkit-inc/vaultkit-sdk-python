from __future__ import annotations

from typing import Any, Dict, List, Optional


def discover_tool_def(
    *,
    dataset_names: Optional[List[str]] = None,
) -> Dict[str, Any]:
    description = (
        "Discover datasets available in VaultKit that you are authorized to query. "
        "Returns dataset names, data sources, and access level (allow/require_approval/deny). "
        "Call this before vaultkit_query if you are unsure which datasets exist."
    )
    if dataset_names:
        description += f" Available datasets include: {', '.join(dataset_names)}."

    return {
        "name": "vaultkit_discover",
        "description": description,
        "input_schema": {
            "type": "object",
            "properties": {
                "environment": {
                    "type": "string",
                    "enum": ["production", "staging", "development"],
                    "default": "production",
                    "description": "Environment to discover datasets in.",
                },
                "requester_region": {
                    "type": "string",
                    "description": "Optional requester region context for policy-aware discovery.",
                },
                "dataset_region": {
                    "type": "string",
                    "description": "Optional dataset region context for policy-aware discovery.",
                },
            },
            "required": [],
        },
    }


def query_tool_def(
    *,
    dataset_names: Optional[List[str]] = None,
    schema_hints: Optional[Dict[str, List[str]]] = None,
) -> Dict[str, Any]:
    # Dataset guidance
    if dataset_names:
        dataset_prop: Dict[str, Any] = {
            "type": "string",
            "enum": dataset_names,
            "description": (
                "The dataset to query. Must be one of the authorized datasets. "
                "Use vaultkit_discover if unsure."
            ),
        }
    else:
        dataset_prop = {
            "type": "string",
            "description": "The dataset to query (use vaultkit_discover to list options).",
        }

    # Field guidance
    fields_desc = "Columns to retrieve. Omit to return all accessible columns."
    if schema_hints:
        examples = []
        for ds, fields in list(schema_hints.items())[:2]:
            examples.append(f"{ds}: [{', '.join(fields[:5])}]")
        if examples:
            fields_desc += f" Example fields — {'; '.join(examples)}."

    filter_condition = {
        "type": "object",
        "properties": {
            "field": {"type": "string"},
            "operator": {
                "type": "string",
                "enum": [
                    "eq",
                    "neq",
                    "gt",
                    "lt",
                    "gte",
                    "lte",
                    "like",
                    "in",
                    "is_null",
                    "is_not_null",
                ],
            },
            "value": {},
        },
        "required": ["field", "operator"],
    }

    filter_group = {
        "type": "object",
        "properties": {
            "logic": {"type": "string", "enum": ["AND", "OR"]},
            "conditions": {
                "type": "array",
                "items": {"oneOf": [filter_condition, {"$ref": "#/$defs/filter_group"}]},
            },
        },
        "required": ["logic", "conditions"],
    }

    return {
        "name": "vaultkit_query",
        "description": (
            "Query a governed dataset through VaultKit. Policies are enforced automatically: "
            "sensitive fields may be masked and some datasets require approval before data is returned. "
            "Returns data or a pending status if approval is required."
        ),
        "input_schema": {
            "$defs": {"filter_group": filter_group},
            "type": "object",
            "properties": {
                "dataset": dataset_prop,
                "fields": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": fields_desc,
                },
                "filters": {
                    "type": "array",
                    "items": {"oneOf": [filter_condition, filter_group]},
                    "description": (
                        "Filter conditions using AQL-style predicates. Supports nested AND/OR groups.\n\n"
                        "Examples:\n"
                        "- Simple: {field: 'age', operator: 'gt', value: 30}\n"
                        "- Nested: {logic: 'OR', conditions: [{...}, {...}]}"
                    ),
                },
                "limit": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 10000,
                    "description": "Maximum number of rows to return.",
                },
                "purpose": {
                    "type": "string",
                    "description": (
                        "Human-readable reason for accessing this data. Required for audit logging and "
                        "approval workflows. Be specific."
                    ),
                },
                "requester_region": {
                    "type": "string",
                    "description": "Optional requester region context for policy evaluation.",
                },
            },
            "required": ["dataset"],
        },
    }


def check_approval_tool_def() -> Dict[str, Any]:
    return {
        "name": "vaultkit_check_approval",
        "description": (
            "Check the approval status of a previously submitted VaultKit query that is pending human approval. "
            "Returns 'pending', 'approved', or 'denied'. If approved, returns the data."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "request_id": {
                    "type": "string",
                    "description": "The request_id returned by vaultkit_query.",
                }
            },
            "required": ["request_id"],
        },
    }
