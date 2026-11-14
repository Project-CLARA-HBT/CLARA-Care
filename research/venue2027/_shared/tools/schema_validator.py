"""CLARA-Care 2027 shared task SH-base_contracts — stdlib JSON Schema validator.

Purpose
-------
Self-contained (standard-library-only) validator for the JSON Schema 2020-12
subset used by the shared v1 base contracts under
``research/venue2027/_shared/schemas/``:

``type``, ``required``, ``enum``, ``const``, ``pattern``, ``minLength``,
``maxLength``, ``minimum``, ``maximum``, ``minItems``, ``maxItems``, ``items``,
``properties``, ``additionalProperties``, ``$ref`` (local ``#/$defs/...`` or
sibling-file ``<name>.schema.json#/$defs/...``), ``oneOf``, ``anyOf``, ``allOf``,
``not`` and ``$defs``.

Allowed input
-------------
A JSON-compatible Python object plus the schema (``dict`` loaded from JSON) and,
for cross-file ``$ref`` resolution, the schema file's own path.

Failure semantics
-----------------
Fail closed. Unknown schema keywords raise ``SchemaError`` with reason code
``UNKNOWN_KEYWORD`` instead of being skipped; unresolvable refs raise
``SchemaError`` (``REF_UNRESOLVED``). Instance errors are collected as
``ValidationError`` items, each carrying a stable uppercase ``reason_code``.
``validate_instance`` returns the sorted tuple of reason codes; ``is_valid`` is a
convenience boolean. Never treat an unvalidated or indeterminate outcome as a
safe rejection.

Version
-------
``SCHEMA_VALIDATOR_VERSION = "1.0.0"`` (additive-only within 1.x).
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VALIDATOR_VERSION = "1.0.0"

SUPPORTED_KEYWORDS: frozenset[str] = frozenset(
    {
        "type",
        "required",
        "enum",
        "const",
        "pattern",
        "minLength",
        "maxLength",
        "minimum",
        "maximum",
        "minItems",
        "maxItems",
        "items",
        "properties",
        "additionalProperties",
        "$ref",
        "oneOf",
        "anyOf",
        "allOf",
        "not",
        "$defs",
        # Annotations / metadata (no validation effect, allowed but ignored):
        "title",
        "description",
        "$schema",
        "$id",
        "format",
    }
)


class SchemaError(ValueError):
    """The *schema itself* is unusable (fail closed, never skip a keyword)."""

    def __init__(self, reason_code: str, message: str) -> None:
        super().__init__(f"{reason_code}: {message}")
        self.reason_code = reason_code


@dataclass(frozen=True)
class ValidationError:
    """One instance error with a stable machine-checkable reason code."""

    reason_code: str
    message: str
    json_path: str

    def to_dict(self) -> dict[str, str]:
        return {
            "reason_code": self.reason_code,
            "message": self.message,
            "json_path": self.json_path,
        }


@dataclass
class _Context:
    schema_dir: Path | None
    root_schema: dict[str, Any]
    errors: list[ValidationError] = field(default_factory=list)
    resolving: frozenset[str] = field(default=frozenset())


def _type_name(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return "string"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    return type(value).__name__


def _check_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        # JSON "integer": ints, and floats with integral value.
        return isinstance(value, bool) is False and (
            isinstance(value, int) or (isinstance(value, float) and value.is_integer())
        )
    if expected == "number":
        return isinstance(value, bool) is False and isinstance(value, int | float)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    raise SchemaError("UNKNOWN_KEYWORD", f"unsupported type {expected!r}")


_SIBLING_REF_RE = re.compile(r"^([A-Za-z0-9_.-]+\.schema\.json)(#.+)?$")


def _resolve_ref(ref: str, ctx: _Context) -> dict[str, Any]:
    sibling = _SIBLING_REF_RE.match(ref)
    if sibling is not None:
        # Sibling-file reference: "<name>.schema.json#/$defs/..." resolved from
        # this schema's directory (keeps cross-schema $defs sharing local).
        if ctx.schema_dir is None:
            raise SchemaError(
                "REF_UNRESOLVED", f"cross-file ref {ref!r} requires schema_path"
            )
        target_file = (ctx.schema_dir / sibling.group(1)).resolve()
        if str(target_file) in ctx.resolving:
            raise SchemaError("REF_UNRESOLVED", f"cyclic $ref at {ref!r}")
        sub_ctx = _Context(
            schema_dir=ctx.schema_dir,
            root_schema=load_json_file(target_file),
            errors=ctx.errors,
            resolving=ctx.resolving | {str(target_file)},
        )
        fragment = sibling.group(2) or "#"
        node = _resolve_pointer(fragment, ref, sub_ctx)
        # Validate the imported file's own keywords too (fail closed).
        for keyword in node:
            if keyword not in SUPPORTED_KEYWORDS:
                raise SchemaError("UNKNOWN_KEYWORD", f"unsupported keyword {keyword!r} in {ref!r}")
        return node
    if not ref.startswith("#"):
        raise SchemaError(
            "UNKNOWN_KEYWORD", f"only local '#/...', sibling-file or '#' refs supported, got {ref!r}"
        )
    return _resolve_pointer(ref, ref, ctx)


def _resolve_pointer(ref: str, original: str, ctx: _Context) -> dict[str, Any]:
    if ref == "#":
        return ctx.root_schema
    fragment = ref[1:]
    if not fragment.startswith("/"):
        raise SchemaError("REF_UNRESOLVED", f"unsupported fragment in {original!r}")
    pointer = [p.replace("~1", "/").replace("~0", "~") for p in fragment.split("/")[1:]]
    node: Any = ctx.root_schema
    for part in pointer:
        if isinstance(node, dict) and part in node:
            node = node[part]
        else:
            raise SchemaError("REF_UNRESOLVED", f"cannot resolve {original!r}")
    if not isinstance(node, dict):
        raise SchemaError("REF_UNRESOLVED", f"ref target of {original!r} is not a schema object")
    return node


def _validate(value: Any, schema: dict[str, Any], ctx: _Context, path: str) -> None:
    if not isinstance(schema, dict):
        raise SchemaError("UNKNOWN_KEYWORD", f"schema must be an object, got {type(schema)!r}")

    for keyword in schema:
        if keyword not in SUPPORTED_KEYWORDS:
            raise SchemaError("UNKNOWN_KEYWORD", f"unsupported schema keyword {keyword!r}")

    if "$ref" in schema:
        target = _resolve_ref(str(schema["$ref"]), ctx)
        _validate(value, target, ctx, path)
        # $ref is applied alongside sibling keywords (2020-12 semantics).

    if "type" in schema:
        expected = schema["type"]
        expected_list = expected if isinstance(expected, list) else [expected]
        if not any(_check_type(value, t) for t in expected_list):
            ctx.errors.append(
                ValidationError(
                    "TYPE_MISMATCH",
                    f"expected type {'/'.join(expected_list)}, got {_type_name(value)}",
                    path,
                )
            )
            return

    if "const" in schema and value != schema["const"]:
        ctx.errors.append(
            ValidationError("CONST_MISMATCH", f"expected const {schema['const']!r}", path)
        )

    if "enum" in schema:
        if not isinstance(schema["enum"], list):
            raise SchemaError("UNKNOWN_KEYWORD", "enum must be an array")
        if not any(value == candidate for candidate in schema["enum"]):
            ctx.errors.append(
                ValidationError("ENUM_MISMATCH", f"value {value!r} not in enum", path)
            )

    if isinstance(value, str):
        if "minLength" in schema and len(value) < int(schema["minLength"]):
            ctx.errors.append(
                ValidationError(
                    "MIN_LENGTH", f"length {len(value)} < minLength {schema['minLength']}", path
                )
            )
        if "maxLength" in schema and len(value) > int(schema["maxLength"]):
            ctx.errors.append(
                ValidationError(
                    "MAX_LENGTH", f"length {len(value)} > maxLength {schema['maxLength']}", path
                )
            )
        if "pattern" in schema and re.search(str(schema["pattern"]), value) is None:
            ctx.errors.append(
                ValidationError(
                    "PATTERN_MISMATCH", f"value {value!r} does not match {schema['pattern']!r}", path
                )
            )

    if isinstance(value, int | float) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            ctx.errors.append(
                ValidationError("MINIMUM", f"value {value} < minimum {schema['minimum']}", path)
            )
        if "maximum" in schema and value > schema["maximum"]:
            ctx.errors.append(
                ValidationError("MAXIMUM", f"value {value} > maximum {schema['maximum']}", path)
            )

    if isinstance(value, list):
        if "minItems" in schema and len(value) < int(schema["minItems"]):
            ctx.errors.append(
                ValidationError(
                    "MIN_ITEMS", f"array has {len(value)} < minItems {schema['minItems']}", path
                )
            )
        if "maxItems" in schema and len(value) > int(schema["maxItems"]):
            ctx.errors.append(
                ValidationError(
                    "MAX_ITEMS", f"array has {len(value)} > maxItems {schema['maxItems']}", path
                )
            )
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for index, item in enumerate(value):
                _validate(item, item_schema, ctx, f"{path}/{index}")
        elif item_schema is not None:
            raise SchemaError("UNKNOWN_KEYWORD", "items must be a schema object")

    if isinstance(value, dict):
        props = schema.get("properties", {})
        if not isinstance(props, dict):
            raise SchemaError("UNKNOWN_KEYWORD", "properties must be an object")
        for name, sub_schema in props.items():
            if name in value and isinstance(sub_schema, dict):
                _validate(value[name], sub_schema, ctx, f"{path}/{name}")
        for req in schema.get("required", []):
            if req not in value:
                ctx.errors.append(
                    ValidationError("REQUIRED_MISSING", f"missing required field {req!r}", path)
                )
        addl = schema.get("additionalProperties", True)
        if addl is False:
            unknown = sorted(set(value) - set(props))
            for name in unknown:
                ctx.errors.append(
                    ValidationError(
                        "ADDITIONAL_PROPERTY", f"unexpected property {name!r}", f"{path}/{name}"
                    )
                )
        elif isinstance(addl, dict):
            known = set(props)
            for name in sorted(set(value) - known):
                _validate(value[name], addl, ctx, f"{path}/{name}")

    combinators = [
        ("allOf", "ALLOF_MISMATCH", all),
        ("anyOf", "ANYOF_MISMATCH", any),
    ]
    for keyword, code, reduce_fn in combinators:
        if keyword in schema:
            branches = schema[keyword]
            if not isinstance(branches, list) or not branches:
                raise SchemaError("UNKNOWN_KEYWORD", f"{keyword} must be a non-empty array")
            outcomes = []
            for branch in branches:
                sub = _Context(ctx.schema_dir, ctx.root_schema)
                _validate(value, branch, sub, path)
                outcomes.append((sub.errors, not sub.errors))
            if not reduce_fn(ok for _, ok in outcomes):
                for errors, ok in outcomes:
                    if not ok:
                        ctx.errors.extend(errors)
                if keyword == "anyOf":
                    ctx.errors.append(
                        ValidationError(code, f"no branch of anyOf matched at {path}", path)
                    )

    if "oneOf" in schema:
        branches = schema["oneOf"]
        if not isinstance(branches, list) or not branches:
            raise SchemaError("UNKNOWN_KEYWORD", "oneOf must be a non-empty array")
        passing: list[list[ValidationError]] = []
        for branch in branches:
            sub = _Context(ctx.schema_dir, ctx.root_schema)
            _validate(value, branch, sub, path)
            if not sub.errors:
                passing.append([])
        if len(passing) != 1:
            ctx.errors.append(
                ValidationError(
                    "ONEOF_MISMATCH",
                    f"exactly one branch must match, {len(passing)} did at {path}",
                    path,
                )
            )

    if "not" in schema:
        sub = _Context(ctx.schema_dir, ctx.root_schema)
        _validate(value, schema["not"], sub, path)
        if not sub.errors:
            ctx.errors.append(
                ValidationError("NOT_MISMATCH", "value matches forbidden 'not' schema", path)
            )


def validate_instance(
    value: Any,
    schema: dict[str, Any],
    *,
    schema_path: str | Path | None = None,
) -> tuple[str, ...]:
    """Validate ``value`` against ``schema``; return sorted reason codes.

    Raises :class:`SchemaError` when the schema itself uses unsupported keywords
    or unresolvable refs (fail closed). Empty tuple == valid.
    """
    schema_dir = Path(schema_path).resolve().parent if schema_path is not None else None
    ctx = _Context(schema_dir=schema_dir, root_schema=schema)
    _validate(value, schema, ctx, "$")
    return tuple(sorted({e.reason_code for e in ctx.errors}))


def validation_errors(
    value: Any,
    schema: dict[str, Any],
    *,
    schema_path: str | Path | None = None,
) -> tuple[ValidationError, ...]:
    """Full error list (reason code + message + JSON path), sorted by path."""
    schema_dir = Path(schema_path).resolve().parent if schema_path is not None else None
    ctx = _Context(schema_dir=schema_dir, root_schema=schema)
    _validate(value, schema, ctx, "$")
    return tuple(sorted(ctx.errors, key=lambda e: (e.json_path, e.reason_code, e.message)))


def is_valid(
    value: Any,
    schema: dict[str, Any],
    *,
    schema_path: str | Path | None = None,
) -> bool:
    """Boolean convenience wrapper; schema errors still raise (fail closed)."""
    return not validate_instance(value, schema, schema_path=schema_path)


def load_json_file(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_schema(path: str | Path) -> dict[str, Any]:
    """Load one schema file from ``_shared/schemas`` as a dict."""
    return load_json_file(Path(path))


def validate_case_v1(case: dict[str, Any], *, schemas_dir: str | Path | None = None) -> bool:
    """Task-contract signature ``validate_case_v1(case)->bool``.

    Returns True iff ``case`` is a valid ``case.v1`` document. Raises
    ``SchemaError`` only for malformed schemas, never for bad instances.
    """
    if schemas_dir is None:
        schemas_dir = Path(__file__).resolve().parents[1] / "schemas"
    schema = load_schema(Path(schemas_dir) / "case.v1.schema.json")
    return is_valid(case, schema, schema_path=Path(schemas_dir) / "case.v1.schema.json")


def validate_run_manifest_v1(
    manifest: dict[str, Any], *, schemas_dir: str | Path | None = None
) -> bool:
    schema_path = Path(schemas_dir or (Path(__file__).resolve().parents[1] / "schemas")) / (
        "run_manifest.v1.schema.json"
    )
    return is_valid(manifest, load_schema(schema_path), schema_path=schema_path)


def validate_oracle_decision_v1(
    decision: dict[str, Any], *, schemas_dir: str | Path | None = None
) -> bool:
    schema_path = Path(schemas_dir or (Path(__file__).resolve().parents[1] / "schemas")) / (
        "oracle_decision.v1.schema.json"
    )
    return is_valid(decision, load_schema(schema_path), schema_path=schema_path)


__all__ = [
    "SCHEMA_VALIDATOR_VERSION",
    "SUPPORTED_KEYWORDS",
    "SchemaError",
    "ValidationError",
    "is_valid",
    "load_schema",
    "validate_case_v1",
    "validate_instance",
    "validate_oracle_decision_v1",
    "validate_run_manifest_v1",
    "validation_errors",
]
