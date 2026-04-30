"""BFCL-style AST equality matchers (ADR-004, research §3.1).

The contract:

* :func:`match_name` is exact string equality.
* :func:`match_arguments` does **AST equality** — keys and values are compared
  structurally, ignoring JSON whitespace and key order, with optional
  schema-driven numeric coercion (string ``"3"`` → ``3`` when the schema
  declares ``number``/``integer``).
* :func:`coerce_tool_call` accepts the OpenAI-shaped envelope produced by
  :class:`AgentGuard.providers.base.ChatResponse` (or our :class:`ToolCall`)
  and returns a :class:`ToolCall`.

The functions here are pure-Python and deterministic — Tier-1 per ADR-019,
no LLM, no network. ``mode="semantic"`` is rejected with a clear error here;
the wrapping keyword in :mod:`AgentGuard.tool_calls.library` decides whether
to escalate to a judge.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from AgentGuard.tool_calls.types import (
    JSON,
    MatchMode,
    MatchResult,
    ToolCall,
)

_NUMERIC_TYPES = frozenset({"number", "integer", "float", "double", "int"})

# ---------------------------------------------------------------------------
# Coercion: turn whatever the provider gave us into a ToolCall
# ---------------------------------------------------------------------------


def coerce_tool_call(value: ToolCall | Mapping[str, Any]) -> ToolCall:
    """Normalise a provider tool-call into a :class:`ToolCall`.

    Accepts:

    * a :class:`ToolCall` (returned unchanged),
    * the OpenAI envelope ``{id, type, function: {name, arguments}}`` where
      ``arguments`` may be a JSON string or already a dict,
    * a flat ``{name, arguments, id?}`` dict.

    Raises :class:`ValueError` for anything else, so a malformed call surfaces
    fast in the test report instead of silently mismatching.
    """
    if isinstance(value, ToolCall):
        return value
    if not isinstance(value, Mapping):
        raise ValueError(f"tool call must be ToolCall or mapping, got {type(value).__name__}")

    func = value.get("function")
    name: Any
    raw_args: Any
    call_id_raw = value.get("id") if "id" in value else None
    call_id = call_id_raw if isinstance(call_id_raw, str) else None

    if isinstance(func, Mapping):
        name = func.get("name")
        raw_args = func.get("arguments", {})
    else:
        name = value.get("name")
        raw_args = value.get("arguments", {})

    if not isinstance(name, str) or not name:
        raise ValueError(f"tool call missing function name: {value!r}")

    args = _parse_arguments(raw_args)
    return ToolCall(name=name, arguments=args, id=call_id)


def _parse_arguments(raw: Any) -> dict[str, JSON]:
    """Parse the ``arguments`` field — JSON string or dict — into a dict.

    Returns ``{}`` for an empty/None payload. Raises :class:`ValueError` for
    invalid JSON; the caller decides whether to surface that as a match
    failure (see :func:`match_arguments`).
    """
    if raw is None or raw == "":
        return {}
    if isinstance(raw, Mapping):
        return dict(raw)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"tool call arguments are not valid JSON: {exc.msg}") from exc
        if not isinstance(parsed, Mapping):
            raise ValueError(
                f"tool call arguments must decode to a JSON object, got {type(parsed).__name__}"
            )
        return dict(parsed)
    raise ValueError(f"unsupported arguments type: {type(raw).__name__}")


# ---------------------------------------------------------------------------
# Normalisation: stable representation for diffs / hashing
# ---------------------------------------------------------------------------


def normalize(args: str | Mapping[str, Any]) -> dict[str, JSON]:
    """Return a deep-sorted, null-stripped representation of ``args``.

    JSON strings are parsed first. Used for stable repr / multiset hashing in
    :mod:`AgentGuard.tool_calls.trajectory`.
    """
    if isinstance(args, str):
        args = _parse_arguments(args)
    return _normalize_value(dict(args))  # type: ignore[return-value]


def _normalize_value(value: Any) -> JSON:
    if value is None:
        return None
    if isinstance(value, Mapping):
        return {k: _normalize_value(v) for k, v in sorted(value.items()) if v is not None}
    if isinstance(value, (list, tuple)):
        return [_normalize_value(v) for v in value]
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float, str)):
        return value
    # Fall back to string for anything exotic — keeps comparisons defined.
    return str(value)


# ---------------------------------------------------------------------------
# AST equality
# ---------------------------------------------------------------------------


def match_name(call: ToolCall | Mapping[str, Any], expected: str) -> bool:
    """Exact string equality on the tool name. No normalisation."""
    try:
        actual = coerce_tool_call(call)
    except ValueError:
        return False
    return actual.name == expected


def match_arguments(
    call: ToolCall | Mapping[str, Any],
    expected: Mapping[str, Any] | str,
    *,
    schema: Mapping[str, Any] | None = None,
    mode: MatchMode = "ast",
) -> bool:
    """Compare actual vs expected arguments per ``mode``.

    * ``strict`` — direct ``==`` after JSON parse, no normalisation.
    * ``ast`` — recursive structural equality with key-order and
      whitespace insensitivity, plus schema-driven numeric coercion.
    * ``semantic`` — not handled here. Raises :class:`ValueError` so the
      caller (the keyword) escalates to the judge.
    """
    if mode == "semantic":
        raise ValueError(
            "semantic comparison is not implemented in bfcl_matcher; "
            "the calling keyword must dispatch to the LLM-as-Judge"
        )

    try:
        actual = coerce_tool_call(call)
        expected_dict = _parse_arguments(expected) if isinstance(expected, str) else dict(expected)
    except ValueError:
        return False

    if mode == "strict":
        return actual.arguments == expected_dict

    return ast_equal(actual.arguments, expected_dict, schema=schema)


def match_arguments_detailed(
    call: ToolCall | Mapping[str, Any],
    expected: Mapping[str, Any] | str,
    *,
    schema: Mapping[str, Any] | None = None,
    mode: MatchMode = "ast",
) -> MatchResult:
    """Same as :func:`match_arguments` but returns a structured :class:`MatchResult`."""
    if mode == "semantic":
        return MatchResult(
            matched=False,
            reasons=("semantic mode requires an LLM judge",),
        )
    try:
        actual = coerce_tool_call(call)
    except ValueError as exc:
        return MatchResult(matched=False, reasons=(str(exc),))
    try:
        expected_dict = _parse_arguments(expected) if isinstance(expected, str) else dict(expected)
    except ValueError as exc:
        return MatchResult(matched=False, reasons=(f"expected: {exc}",))

    diff = {
        "actual": _normalize_value(actual.arguments),
        "expected": _normalize_value(expected_dict),
    }

    if mode == "strict":
        ok = actual.arguments == expected_dict
        return MatchResult(
            matched=ok,
            reasons=() if ok else ("strict equality failed",),
            diff=diff,
        )

    reasons: list[str] = []
    ok = _ast_equal_with_reasons(
        actual.arguments,
        expected_dict,
        schema=schema or {},
        path="",
        reasons=reasons,
    )
    return MatchResult(matched=ok, reasons=tuple(reasons), diff=diff)


def ast_equal(
    a: Any,
    b: Any,
    *,
    schema: Mapping[str, Any] | None = None,
) -> bool:
    """Recursive structural equality with optional schema-driven coercion.

    Lists are ordered (BFCL spec); dicts compared by key set + per-value AST.
    """
    return _ast_equal_with_reasons(a, b, schema=schema or {}, path="", reasons=[])


def _ast_equal_with_reasons(
    a: Any,
    b: Any,
    *,
    schema: Mapping[str, Any],
    path: str,
    reasons: list[str],
) -> bool:
    a_n = _coerce_for_schema(a, schema)
    b_n = _coerce_for_schema(b, schema)

    # Booleans are *not* ints for our purposes (json: true ≠ 1).
    if isinstance(a_n, bool) or isinstance(b_n, bool):
        if isinstance(a_n, bool) != isinstance(b_n, bool) or a_n != b_n:
            reasons.append(f"{path or '<root>'}: bool mismatch ({a_n!r} vs {b_n!r})")
            return False
        return True

    if isinstance(a_n, Mapping) and isinstance(b_n, Mapping):
        a_keys = set(a_n.keys())
        b_keys = set(b_n.keys())
        if a_keys != b_keys:
            extra = a_keys - b_keys
            missing = b_keys - a_keys
            if extra:
                reasons.append(f"{path or '<root>'}: extra keys {sorted(extra)}")
            if missing:
                reasons.append(f"{path or '<root>'}: missing keys {sorted(missing)}")
            return False
        sub_props = _sub_properties(schema)
        ok = True
        for key in sorted(a_keys):
            child_schema = sub_props.get(key, {})
            if not _ast_equal_with_reasons(
                a_n[key],
                b_n[key],
                schema=child_schema,
                path=f"{path}.{key}" if path else key,
                reasons=reasons,
            ):
                ok = False
        return ok

    if isinstance(a_n, Sequence) and not isinstance(a_n, (str, bytes)):
        if not (isinstance(b_n, Sequence) and not isinstance(b_n, (str, bytes))):
            reasons.append(f"{path or '<root>'}: type mismatch (list vs {type(b_n).__name__})")
            return False
        if len(a_n) != len(b_n):
            reasons.append(
                f"{path or '<root>'}: length mismatch ({len(a_n)} vs {len(b_n)})"
            )
            return False
        item_schema = (
            schema.get("items", {}) if isinstance(schema, Mapping) else {}
        )
        ok = True
        for i, (ai, bi) in enumerate(zip(a_n, b_n, strict=True)):
            if not _ast_equal_with_reasons(
                ai,
                bi,
                schema=item_schema,
                path=f"{path}[{i}]",
                reasons=reasons,
            ):
                ok = False
        return ok

    if isinstance(a_n, (int, float)) and isinstance(b_n, (int, float)):
        # Numeric equality with float tolerance (1.0 == 1).
        if a_n == b_n:
            return True
        reasons.append(f"{path or '<root>'}: numeric mismatch ({a_n!r} vs {b_n!r})")
        return False

    if a_n == b_n:
        return True

    reasons.append(f"{path or '<root>'}: value mismatch ({a_n!r} vs {b_n!r})")
    return False


def _coerce_for_schema(value: Any, schema: Mapping[str, Any]) -> Any:
    """Apply minimal numeric / boolean coercion when the schema declares it.

    BFCL only requires this at the leaf (string-encoded numbers from some
    tool-calling models). We never coerce ``true``/``false`` strings — those
    are the model's responsibility.
    """
    if not isinstance(schema, Mapping):
        return value
    declared = schema.get("type")
    if not isinstance(declared, str):
        return value
    declared_l = declared.lower()
    floatish = {"number", "float", "double"}
    if isinstance(value, str) and declared_l in _NUMERIC_TYPES:
        try:
            if "." in value or declared_l in floatish:
                return float(value)
            return int(value)
        except ValueError:
            return value
    if isinstance(value, int) and not isinstance(value, bool) and declared_l in floatish:
        return float(value)
    return value


def _sub_properties(schema: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    """Return ``schema['properties']`` as a dict mapping prop → sub-schema."""
    if not isinstance(schema, Mapping):
        return {}
    props = schema.get("properties")
    if isinstance(props, Mapping):
        return {k: v for k, v in props.items() if isinstance(v, Mapping)}
    # Allow callers to pass {"properties": {...}, ...} or just {...} directly.
    if all(isinstance(v, Mapping) for v in schema.values()):
        return {k: v for k, v in schema.items() if isinstance(v, Mapping)}
    return {}


# ---------------------------------------------------------------------------
# Multiset equality for parallel calls (used by trajectory.match_parallel too)
# ---------------------------------------------------------------------------


def call_signature(call: ToolCall | Mapping[str, Any]) -> tuple[str, str]:
    """Return a stable ``(name, json-of-normalised-args)`` signature.

    Two tool calls with the same name and AST-equal arguments produce the
    same signature, so multiset equality reduces to ``Counter`` comparison.
    """
    coerced = coerce_tool_call(call)
    return coerced.name, json.dumps(_normalize_value(coerced.arguments), sort_keys=True)


__all__ = [
    "ast_equal",
    "call_signature",
    "coerce_tool_call",
    "match_arguments",
    "match_arguments_detailed",
    "match_name",
    "normalize",
]
