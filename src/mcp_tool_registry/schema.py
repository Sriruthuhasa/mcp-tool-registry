"""Minimal JSON-schema validator (the subset tool arguments usually need).

Supported keywords: type, properties, required, additionalProperties,
items, enum, minimum, maximum, minLength, maxLength, default.
"""

from __future__ import annotations

from typing import Any

_TYPES = {
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "object": dict,
    "array": list,
    "null": type(None),
}


class SchemaError(ValueError):
    """Raised when a value does not match a schema. Holds every problem found."""

    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def _type_ok(value: Any, expected: str) -> bool:
    # bool is a subclass of int in Python; JSON keeps them apart.
    if expected in ("integer", "number") and isinstance(value, bool):
        return False
    py = _TYPES.get(expected)
    if py is None:
        raise ValueError(f"unsupported schema type: {expected!r}")
    return isinstance(value, py)


def _check(value: Any, schema: dict, path: str, errors: list[str]) -> None:
    expected = schema.get("type")
    if expected is not None:
        options = expected if isinstance(expected, list) else [expected]
        if not any(_type_ok(value, t) for t in options):
            errors.append(f"{path}: expected {'/'.join(options)}, got {type(value).__name__}")
            return

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in {schema['enum']}")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value} < minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: {value} > maximum {schema['maximum']}")

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: shorter than {schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: longer than {schema['maxLength']}")

    if isinstance(value, dict):
        props = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in value:
                errors.append(f"{path}.{name}: required")
        for name, sub in value.items():
            if name in props:
                _check(sub, props[name], f"{path}.{name}", errors)
            elif schema.get("additionalProperties", True) is False:
                errors.append(f"{path}.{name}: unexpected property")

    if isinstance(value, list) and "items" in schema:
        for i, item in enumerate(value):
            _check(item, schema["items"], f"{path}[{i}]", errors)


def apply_defaults(value: dict, schema: dict) -> dict:
    """Return a copy of an object with top-level defaults filled in."""
    out = dict(value)
    for name, sub in schema.get("properties", {}).items():
        if name not in out and "default" in sub:
            out[name] = sub["default"]
    return out


def validate(value: Any, schema: dict) -> None:
    """Raise SchemaError listing all problems, or return None if valid."""
    errors: list[str] = []
    _check(value, schema, "$", errors)
    if errors:
        raise SchemaError(errors)
