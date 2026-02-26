from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

@dataclass(frozen=True)
class DatasetSchema:
    dataset: str
    datasource: str
    fields: List[Dict[str, Any]]
    correlation_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DatasetSchema":
        dataset = data.get("dataset")
        datasource = data.get("datasource")

        if not dataset or not datasource:
            raise ValueError("DatasetSchema requires 'dataset' and 'datasource'")

        raw_fields = data.get("fields")
        fields = raw_fields if isinstance(raw_fields, list) else []

        return cls(
            dataset=dataset,
            datasource=datasource,
            fields=fields,
            correlation_id=data.get("correlation_id"),
        )

    @property
    def field_names(self) -> List[str]:
        return [
            f.get("name")
            for f in self.fields
            if isinstance(f, dict) and f.get("name")
        ]

    @property
    def field_map(self) -> Dict[str, Dict[str, Any]]:
        return {
            f["name"]: f
            for f in self.fields
            if isinstance(f, dict) and "name" in f
        }

    @property
    def field_summaries(self) -> List[str]:
        """
        Human-readable summaries for LLM grounding.
        """
        summaries = []

        for f in self.fields:
            if not isinstance(f, dict):
                continue

            name = f.get("name")
            if not name:
                continue

            parts = [name]

            if f.get("masked"):
                parts.append("(masked)")

            if f.get("visibility") == "deny":
                parts.append("(restricted)")

            if f.get("sensitivity"):
                parts.append(f"(sensitivity: {f['sensitivity']})")

            summaries.append(" ".join(parts))

        return summaries
