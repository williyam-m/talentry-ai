"""Candidate schema accessor + lightweight JSON-Schema validator.

We deliberately avoid pulling in `jsonschema` (and its `referencing`,
`attrs`, `rpds-py` Rust wheel) just to validate a handful of fields -
keeping the runtime image lean is a hard production requirement for the
HF Space cold-start budget. Instead we ship a *focused* validator that
understands exactly the subset of JSON-Schema draft-07 used by the
official ``candidate_schema.json``:

    type, required, properties, items, enum, minimum, maximum,
    minItems, maxItems, additionalProperties, pattern, format("date")

The validator surfaces *every* error (it does not bail on first) and
returns structured `SchemaError` objects so the UI can render a
git-diff-style payload describing what's missing / extra / wrong
between the candidate's record and the expected shape.

"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

# ─────────────────────────────────────────────────────────────────────────────
# Schema loading

_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "resources" / "candidate_schema.json"


@lru_cache(maxsize=1)
def load_schema() -> dict[str, Any]:
    """Return the default candidate JSON-Schema (cached)."""
    if not _SCHEMA_PATH.exists():
        raise FileNotFoundError(
            f"candidate_schema.json missing from package resources at {_SCHEMA_PATH}"
        )
    with _SCHEMA_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


# ─────────────────────────────────────────────────────────────────────────────
# Validator


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(slots=True)
class SchemaError:
    """One mismatch between an instance and the schema.

    Attributes
    ----------
    path :
        Dotted/bracketed JSON pointer-ish path (e.g. ``profile.summary``,
        ``career_history[0].duration_months``).
    code :
        Machine-readable error code: ``missing_required``, ``wrong_type``,
        ``enum_violation``, ``out_of_range``, ``pattern_mismatch``,
        ``bad_date``, ``unknown_property``, ``too_few_items``,
        ``too_many_items``.
    message :
        Human-readable explanation.
    expected :
        What the schema expects (string-rendered).
    actual :
        What was found (string-rendered, truncated).
    """

    path: str
    code: str
    message: str
    expected: str = ""
    actual: str = ""

    def as_dict(self) -> dict[str, str]:
        return asdict(self)


def _type_matches(value: Any, expected: str | list[str]) -> bool:
    types = expected if isinstance(expected, list) else [expected]
    for t in types:
        if t == "null" and value is None:
            return True
        if t == "string" and isinstance(value, str):
            return True
        if t == "boolean" and isinstance(value, bool):
            return True
        if t == "integer" and isinstance(value, int) and not isinstance(value, bool):
            return True
        if t == "number" and isinstance(value, (int, float)) and not isinstance(value, bool):
            return True
        if t == "array" and isinstance(value, list):
            return True
        if t == "object" and isinstance(value, dict):
            return True
    return False


def _short(value: Any, limit: int = 80) -> str:
    s = json.dumps(value, default=str, ensure_ascii=False)
    return s if len(s) <= limit else s[: limit - 1] + "…"


def _walk(
    instance: Any,
    schema: dict[str, Any],
    path: str,
    errors: list[SchemaError],
) -> None:
    expected_type = schema.get("type")
    if expected_type is not None and not _type_matches(instance, expected_type):
        errors.append(
            SchemaError(
                path=path or "$",
                code="wrong_type",
                message=f"expected type {expected_type!r}",
                expected=str(expected_type),
                actual=type(instance).__name__,
            )
        )
        return  # further checks would be misleading

    # enum
    if "enum" in schema and instance is not None:
        if instance not in schema["enum"]:
            errors.append(
                SchemaError(
                    path=path or "$",
                    code="enum_violation",
                    message="value is not one of the allowed enum entries",
                    expected=", ".join(map(repr, schema["enum"])),
                    actual=_short(instance),
                )
            )

    # numeric ranges
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(
                SchemaError(
                    path=path or "$",
                    code="out_of_range",
                    message=f"value is below minimum {schema['minimum']}",
                    expected=f">= {schema['minimum']}",
                    actual=str(instance),
                )
            )
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(
                SchemaError(
                    path=path or "$",
                    code="out_of_range",
                    message=f"value is above maximum {schema['maximum']}",
                    expected=f"<= {schema['maximum']}",
                    actual=str(instance),
                )
            )

    # string format / pattern
    if isinstance(instance, str):
        pattern = schema.get("pattern")
        if pattern and not re.match(pattern, instance):
            errors.append(
                SchemaError(
                    path=path or "$",
                    code="pattern_mismatch",
                    message=f"does not match required pattern {pattern!r}",
                    expected=pattern,
                    actual=_short(instance),
                )
            )
        if schema.get("format") == "date" and not _DATE_RE.match(instance):
            errors.append(
                SchemaError(
                    path=path or "$",
                    code="bad_date",
                    message="not an ISO-8601 date (YYYY-MM-DD)",
                    expected="YYYY-MM-DD",
                    actual=_short(instance),
                )
            )

    # object
    if isinstance(instance, dict):
        required = schema.get("required") or []
        for key in required:
            if key not in instance:
                errors.append(
                    SchemaError(
                        path=f"{path}.{key}" if path else key,
                        code="missing_required",
                        message=f"required property {key!r} is missing",
                        expected=key,
                        actual="<missing>",
                    )
                )
        props = schema.get("properties") or {}
        additional = schema.get("additionalProperties")
        for k, v in instance.items():
            sub = f"{path}.{k}" if path else k
            if k in props:
                _walk(v, props[k], sub, errors)
            elif additional is False:
                errors.append(
                    SchemaError(
                        path=sub,
                        code="unknown_property",
                        message=f"property {k!r} is not declared in the schema",
                        expected="<declared property>",
                        actual=k,
                    )
                )
            elif isinstance(additional, dict):
                _walk(v, additional, sub, errors)

    # array
    if isinstance(instance, list):
        items = schema.get("items")
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errors.append(
                SchemaError(
                    path=path or "$",
                    code="too_few_items",
                    message=f"array has {len(instance)} items, schema requires >= {schema['minItems']}",
                    expected=f">= {schema['minItems']}",
                    actual=str(len(instance)),
                )
            )
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errors.append(
                SchemaError(
                    path=path or "$",
                    code="too_many_items",
                    message=f"array has {len(instance)} items, schema allows <= {schema['maxItems']}",
                    expected=f"<= {schema['maxItems']}",
                    actual=str(len(instance)),
                )
            )
        if isinstance(items, dict):
            for i, el in enumerate(instance):
                _walk(el, items, f"{path}[{i}]", errors)


def validate_candidate(instance: Any) -> list[SchemaError]:
    """Validate one candidate record and return all errors (empty == valid)."""
    errors: list[SchemaError] = []
    _walk(instance, load_schema(), "", errors)
    return errors


@dataclass(slots=True)
class BatchValidationReport:
    n_total: int
    n_valid: int
    n_invalid: int
    errors_by_row: list[dict[str, Any]] = field(default_factory=list)
    first_invalid_index: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "n_total": self.n_total,
            "n_valid": self.n_valid,
            "n_invalid": self.n_invalid,
            "first_invalid_index": self.first_invalid_index,
            "errors_by_row": self.errors_by_row,
        }


def validate_batch(records: list[dict[str, Any]], *, max_rows_reported: int = 25) -> BatchValidationReport:
    """Validate up to N records, returning a compact report for the UI."""
    n_valid = 0
    rows: list[dict[str, Any]] = []
    first_invalid: int | None = None
    for i, rec in enumerate(records):
        errs = validate_candidate(rec)
        if not errs:
            n_valid += 1
            continue
        if first_invalid is None:
            first_invalid = i
        if len(rows) < max_rows_reported:
            rows.append(
                {
                    "index": i,
                    "candidate_id": (rec or {}).get("candidate_id") if isinstance(rec, dict) else None,
                    "errors": [e.as_dict() for e in errs[:25]],
                    "truncated": len(errs) > 25,
                }
            )
    return BatchValidationReport(
        n_total=len(records),
        n_valid=n_valid,
        n_invalid=len(records) - n_valid,
        errors_by_row=rows,
        first_invalid_index=first_invalid,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Diff utilities - used by the UI to render a git diff style report.



def _flatten(value: Any, prefix: str = "", out: dict[str, Any] | None = None) -> dict[str, Any]:
    if out is None:
        out = {}
    if isinstance(value, dict):
        if not value:
            out[prefix or "$"] = {}
        for k, v in value.items():
            p = f"{prefix}.{k}" if prefix else k
            _flatten(v, p, out)
    elif isinstance(value, list):
        if not value:
            out[prefix or "$"] = []
        for i, el in enumerate(value):
            _flatten(el, f"{prefix}[{i}]", out)
    else:
        out[prefix or "$"] = value
    return out


def _schema_skeleton(schema: dict[str, Any]) -> Any:
    """Generate a minimal valid example instance from the schema."""
    t = schema.get("type")
    if isinstance(t, list):
        t = next((x for x in t if x != "null"), t[0])
    if t == "object":
        out: dict[str, Any] = {}
        required = schema.get("required") or []
        props = schema.get("properties") or {}
        for k in required:
            if k in props:
                out[k] = _schema_skeleton(props[k])
            else:
                out[k] = None
        return out
    if t == "array":
        items = schema.get("items")
        min_items = schema.get("minItems", 0)
        if isinstance(items, dict) and min_items > 0:
            return [_schema_skeleton(items)]
        return []
    if "enum" in schema:
        return schema["enum"][0]
    if t == "string":
        if schema.get("format") == "date":
            return "YYYY-MM-DD"
        if schema.get("pattern"):
            return f"<{schema['pattern']}>"
        return ""
    if t == "integer":
        return schema.get("minimum", 0)
    if t == "number":
        return float(schema.get("minimum", 0))
    if t == "boolean":
        return False
    return None


def diff_against_schema(instance: Any) -> dict[str, Any]:
    """Return a UI-friendly green/red diff payload.

    Output shape::

        {
          "expected": [{"path": ..., "value": ...}, ...],
          "actual":   [{"path": ..., "value": ...}, ...],
          "lines":    [{"kind": "match|missing|extra|wrong", "path": ..., ...}, ...]
        }
    """
    schema = load_schema()
    skeleton = _schema_skeleton(schema)
    expected_flat = _flatten(skeleton)
    actual_flat = _flatten(instance if isinstance(instance, dict) else {})

    paths = sorted(set(expected_flat) | set(actual_flat))
    lines: list[dict[str, Any]] = []
    for p in paths:
        in_exp = p in expected_flat
        in_act = p in actual_flat
        if in_exp and in_act:
            lines.append(
                {
                    "kind": "match",
                    "path": p,
                    "expected": expected_flat[p],
                    "actual": actual_flat[p],
                }
            )
        elif in_exp and not in_act:
            lines.append({"kind": "missing", "path": p, "expected": expected_flat[p]})
        else:
            lines.append({"kind": "extra", "path": p, "actual": actual_flat[p]})

    return {
        "expected_skeleton": skeleton,
        "actual": instance,
        "lines": lines,
    }
