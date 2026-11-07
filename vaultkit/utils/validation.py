from __future__ import annotations

from typing import Any, Dict, Optional

from vaultkit.errors.base import ErrorContext
from vaultkit.errors.exceptions import ValidationError


def require_str(name: str, value: Optional[str]) -> str:
    if value is None:
        raise ValidationError(
            f"{name} is required",
            context=ErrorContext(raw={name: value}),
        )

    result = str(value).strip()
    if not result:
        raise ValidationError(
            f"{name} cannot be empty",
            context=ErrorContext(raw={name: value}),
        )

    return result


def require_dict(name: str, value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError(
            f"{name} must be an object/dict",
            context=ErrorContext(raw={name: value}),
        )
    return value


def require_list(name: str, value: Any) -> list:
    if not isinstance(value, list):
        raise ValidationError(
            f"{name} must be a list",
            context=ErrorContext(raw={name: value}),
        )
    return value


def validate_limit(value: Optional[int]) -> Optional[int]:
    if value is None:
        return None

    if not isinstance(value, int):
        raise ValidationError(
            "limit must be an integer",
            context=ErrorContext(raw=value),
        )

    if value <= 0:
        raise ValidationError(
            "limit must be greater than 0",
            context=ErrorContext(raw=value),
        )

    if value > 10000:
        raise ValidationError(
            "limit cannot exceed 10000",
            context=ErrorContext(raw=value),
        )

    return value


def validate_filters(value: Optional[Any]) -> Optional[list]:
    if value is None:
        return None

    if not isinstance(value, list):
        raise ValidationError(
            "filters must be a list",
            context=ErrorContext(raw=value),
        )

    # light structural validation
    for f in value:
        if not isinstance(f, dict):
            raise ValidationError(
                "each filter must be an object",
                context=ErrorContext(raw=f),
            )

    return value


# Analytical clauses. Only the shape is checked here; the control plane
# validates functions, fields and operators and returns a clear error.

def _require_list_of_dicts(name: str, value: Optional[Any]) -> Optional[list]:
    if value is None:
        return None

    if not isinstance(value, list):
        raise ValidationError(
            f"{name} must be a list",
            context=ErrorContext(raw=value),
        )

    for item in value:
        if not isinstance(item, dict):
            raise ValidationError(
                f"each {name} entry must be an object",
                context=ErrorContext(raw=item),
            )

    return value


def validate_aggregates(value: Optional[Any]) -> Optional[list]:
    value = _require_list_of_dicts("aggregates", value)
    if value is None:
        return None

    if not value:
        raise ValidationError(
            "aggregates cannot be empty",
            context=ErrorContext(raw=value),
        )

    for agg in value:
        if not agg.get("func") or not agg.get("field"):
            raise ValidationError(
                "each aggregate needs 'func' and 'field'",
                context=ErrorContext(raw=agg),
            )

    return value


# Units a group_by time bucket can use. The control plane checks the field is
# a timestamp or date column and that the time zone exists.
TIME_BUCKETS = ("day", "week", "month", "quarter", "year")
TIME_BUCKET_KEYS = {"field", "bucket", "alias", "timezone"}


def validate_group_by(value: Optional[Any]) -> Optional[list]:
    if value is None:
        return None

    if not isinstance(value, list):
        raise ValidationError(
            "group_by must be a list of field names or time buckets",
            context=ErrorContext(raw=value),
        )

    for entry in value:
        if isinstance(entry, dict):
            _validate_time_bucket(entry)
        elif not (isinstance(entry, str) and entry.strip()):
            raise ValidationError(
                "group_by must be a list of field names or time buckets",
                context=ErrorContext(raw=value),
            )

    return value


def _validate_time_bucket(entry: Dict[str, Any]) -> None:
    unknown = set(entry) - TIME_BUCKET_KEYS
    if unknown:
        raise ValidationError(
            f"group_by time bucket has unknown keys: {', '.join(sorted(unknown))}",
            context=ErrorContext(raw=entry),
        )

    field = entry.get("field")
    if not isinstance(field, str) or not field.strip():
        raise ValidationError(
            "group_by time bucket needs a 'field'",
            context=ErrorContext(raw=entry),
        )

    bucket = entry.get("bucket")
    if not isinstance(bucket, str) or bucket.lower() not in TIME_BUCKETS:
        raise ValidationError(
            f"group_by time bucket must be one of {', '.join(TIME_BUCKETS)}",
            context=ErrorContext(raw=entry),
        )

    for key in ("alias", "timezone"):
        if key in entry and not (isinstance(entry[key], str) and entry[key].strip()):
            raise ValidationError(
                f"group_by time bucket '{key}' must be a non-empty string",
                context=ErrorContext(raw=entry),
            )


def validate_having(value: Optional[Any]) -> Optional[list]:
    return _require_list_of_dicts("having", value)


def validate_order_by(value: Optional[Any]) -> Optional[Dict[str, Any]]:
    if value is None:
        return None

    if not isinstance(value, dict) or not value.get("column"):
        raise ValidationError(
            "order_by must be an object with a 'column'",
            context=ErrorContext(raw=value),
        )

    return value
