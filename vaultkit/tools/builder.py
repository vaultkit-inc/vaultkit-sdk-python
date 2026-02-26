from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Optional

from .adapters import ToolProvider
from .adapters.anthropic import to_anthropic_tool
from .adapters.openai import to_openai_tool
from .definitions import (
    check_approval_tool_def,
    discover_tool_def,
    query_tool_def,
)

if TYPE_CHECKING:
    from vaultkit.client import VaultKitClient


class ToolBuilder:
    """
    Generates provider-specific tool schemas scoped to what the agent
    is authorized to access.

    Provider formats:
      - OpenAI: tools=[{type:"function", function:{name,description,parameters}}]
      - Anthropic: tools=[{name,description,input_schema}]
      - Raw: canonical tool defs=[{name,description,input_schema}]
    """

    MAX_SCHEMA_HINTS = 10  # prevent N+1 explosion

    def __init__(self, client: "VaultKitClient") -> None:
        self._client = client

    def build(
        self,
        *,
        provider: ToolProvider = ToolProvider.OPENAI,
        environment: str = "production",
        include_discover: bool = True,
        include_query: bool = True,
        include_check_approval: bool = False,
        datasets: Optional[List[str]] = None,
        fetch_schema_hints: bool = True,
        requester_region: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        # Build canonical tool defs
        resolved_datasets = datasets or self._fetch_dataset_names(
            environment=environment,
            requester_region=requester_region,
        )

        schema_hints: Optional[Dict[str, List[str]]] = None
        if fetch_schema_hints and resolved_datasets:
            schema_hints = self._fetch_schema_hints(
                resolved_datasets,
                environment=environment,
                requester_region=requester_region,
            )

        canonical: List[Dict[str, Any]] = []

        if include_discover:
            canonical.append(discover_tool_def(dataset_names=resolved_datasets))

        if include_query:
            canonical.append(
                query_tool_def(dataset_names=resolved_datasets, schema_hints=schema_hints)
            )

        if include_check_approval:
            canonical.append(check_approval_tool_def())

        # Convert to provider format
        if provider == ToolProvider.RAW:
            return canonical
        if provider == ToolProvider.ANTHROPIC:
            return [to_anthropic_tool(t) for t in canonical]
        # default OPENAI
        return [to_openai_tool(t) for t in canonical]

    def build_minimal(self, *, provider: ToolProvider = ToolProvider.OPENAI) -> List[Dict[str, Any]]:
        """Fast startup: just vaultkit_query, no registry calls."""
        canonical = [query_tool_def()]
        if provider == ToolProvider.RAW:
            return canonical
        if provider == ToolProvider.ANTHROPIC:
            return [to_anthropic_tool(t) for t in canonical]
        return [to_openai_tool(t) for t in canonical]

    # private

    def _fetch_dataset_names(
        self,
        *,
        environment: str,
        requester_region: Optional[str],
    ) -> List[str]:
        try:
            infos = self._client.datasets(
                environment=environment,
                requester_region=requester_region,
            )
            return [d.dataset for d in infos]
        except Exception:
            return []

    def _fetch_schema_hints(
        self,
        dataset_names: List[str],
        *,
        environment: str,
        requester_region: Optional[str],
    ) -> Dict[str, List[str]]:
        hints: Dict[str, List[str]] = {}

        for dataset in dataset_names[: self.MAX_SCHEMA_HINTS]:
            try:
                schema = self._client.schema(
                    dataset,
                    environment=environment,
                    requester_region=requester_region,
                )
                summaries = getattr(schema, "field_summaries", None)
                hints[dataset] = summaries if isinstance(summaries, list) else schema.field_names
            except Exception:
                continue

        return hints
