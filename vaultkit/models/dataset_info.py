from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class DatasetInfo:
    dataset: str
    datasource: str
    visibility: Optional[str] = None
    correlation_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data):
        dataset = data.get("name") or data.get("dataset")
        datasource = data.get("datasource")

        if not dataset or not datasource:
            raise ValueError("DatasetInfo requires 'name'/'dataset' and 'datasource'")

        return cls(
            dataset=dataset,
            datasource=datasource,
            visibility=data.get("visibility"),
            correlation_id=data.get("correlation_id"),
        )
