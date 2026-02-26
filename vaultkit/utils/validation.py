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
