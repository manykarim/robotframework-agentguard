"""Secret + PII + token redaction for trajectories.

Three modes:

- ``strict``    — replace match with ``<REDACTED:KIND>``.
- ``balanced``  — keep the first 2 and last 4 characters, mask the middle
  (matches ``policy-defaults.md`` §5 reviewer-correlation requirement
  via the ``hash`` mode where determinism matters more than masking).
- ``tokenize``  — replace with ``<REDACTED:KIND:sha256[:8]>`` so identical
  secrets dedupe across a trajectory without leaking the value
  (the spec's primary mode).

Patterns are intentionally conservative: false positives on customer data
are preferable to false negatives on credentials.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping
from typing import Any, Literal, NamedTuple, cast

Mode = Literal["strict", "balanced", "tokenize"]


class _Pattern(NamedTuple):
    kind: str
    regex: re.Pattern[str]
    extra_validator: str = ""  # Empty = no extra check; "luhn" = credit-card


def _luhn_ok(digits: str) -> bool:
    s = [int(c) for c in digits if c.isdigit()]
    if len(s) < 13:
        return False
    checksum = 0
    parity = len(s) % 2
    for i, d in enumerate(s):
        if i % 2 == parity:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


# Order matters: more specific patterns first.
_PATTERNS: tuple[_Pattern, ...] = (
    _Pattern("ANTHROPIC_KEY", re.compile(r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b")),
    _Pattern("OPENAI_KEY", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9]{20,}\b")),
    _Pattern("BEARER_TOKEN", re.compile(r"\bBearer\s+[A-Za-z0-9._\-]{16,}\b")),
    _Pattern(
        "JWT",
        re.compile(r"\beyJ[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}\b"),
    ),
    _Pattern("AWS_ACCESS_KEY", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    _Pattern("GITHUB_PAT", re.compile(r"\bghp_[A-Za-z0-9]{36}\b")),
    _Pattern(
        "SLACK_TOKEN",
        re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    ),
    _Pattern("PEM_BLOCK", re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----")),
    _Pattern(
        "ENV_SECRET",
        re.compile(
            r"\b(?:[A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|PASSWD))\s*=\s*"
            r"(['\"]?)([A-Za-z0-9._\-/+=]{8,})\1"
        ),
    ),
    _Pattern("EMAIL", re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b")),
    _Pattern("PHONE", re.compile(r"(?<!\d)(?:\+?\d{1,3}[ \-.]?)?\(?\d{3}\)?[ \-.]?\d{3}[ \-.]?\d{4}(?!\d)")),
    _Pattern("SSN", re.compile(r"\b(?!000|666)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b")),
    _Pattern(
        "CREDIT_CARD",
        re.compile(r"\b(?:\d[ \-]?){13,19}\b"),
        extra_validator="luhn",
    ),
    _Pattern("HOME_PATH", re.compile(r"/(?:Users|home)/[A-Za-z0-9._\-]+")),
)


def _hash_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]


def _balanced_mask(value: str) -> str:
    if len(value) <= 6:
        return "*" * len(value)
    return f"{value[:2]}{'*' * (len(value) - 6)}{value[-4:]}"


def _replace(match: str, kind: str, mode: Mode) -> str:
    if mode == "strict":
        return f"<REDACTED:{kind}>"
    if mode == "balanced":
        return _balanced_mask(match)
    return f"<REDACTED:{kind}:{_hash_token(match)}>"


def redact(text: str, mode: Mode = "tokenize") -> str:
    """Return ``text`` with secrets/PII replaced according to ``mode``."""
    if not text:
        return text
    out = text
    for pat in _PATTERNS:

        def _sub(m: re.Match[str], k: str = pat.kind, v: str = pat.extra_validator) -> str:
            value = m.group(0)
            if v == "luhn" and not _luhn_ok(value):
                return value
            return _replace(value, k, mode)

        out = pat.regex.sub(_sub, out)
    return out


def redact_dict(obj: Any, mode: Mode = "tokenize") -> Any:
    """Recursively redact every string value inside a JSON-shaped object."""
    if isinstance(obj, str):
        return redact(obj, mode)
    if isinstance(obj, Mapping):
        return {k: redact_dict(v, mode) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        seq = [redact_dict(v, mode) for v in obj]
        return type(obj)(seq) if isinstance(obj, tuple) else seq
    return obj


def find_secrets(text: str) -> list[tuple[str, str]]:
    """Return ``[(kind, value), ...]`` for every secret/PII match in ``text``.

    Used by ``Trajectory Should Not Leak Secrets`` to assert without redacting.
    """
    if not text:
        return []
    found: list[tuple[str, str]] = []
    for pat in _PATTERNS:
        for m in pat.regex.finditer(text):
            value = m.group(0)
            if pat.extra_validator == "luhn" and not _luhn_ok(value):
                continue
            found.append((pat.kind, value))
    return found


def serialize_trajectory(trajectory: list[dict[str, Any]] | str) -> str:
    """Best-effort serialisation so callers can pass Robot lists or strings."""
    if isinstance(trajectory, str):
        return trajectory
    import json

    return json.dumps(cast(list[Any], trajectory), default=str, ensure_ascii=False)
