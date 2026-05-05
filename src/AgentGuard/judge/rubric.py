"""Rubric loading + judge-prompt formatting (ADR-011, research §3.2).

Rubrics are *classification* schemas — each criterion has a small set of
named labels (``good`` / ``partial`` / ``bad``) with attached scores in
``[0.0, 1.0]``. Numeric ratings are deliberately not supported; Hamel Husain
and Braintrust both report classification is more reliable than 1-7 scoring.

Markdown source format::

    # Rubric: Tool output equivalence

    ## correctness
    Does the output convey the same factual content as the reference?
    - good [1.0]: matches the reference within paraphrase tolerance
    - partial [0.5]: missing a non-essential detail
    - bad [0.0]: contradicts or omits an essential detail

YAML source format::

    name: Tool output equivalence
    criteria:
      - name: correctness
        description: Does the output convey ...
        labels:
          - {value: good, score: 1.0, description: matches the reference …}
          - {value: partial, score: 0.5, description: missing …}
          - {value: bad, score: 0.0, description: contradicts …}
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True, frozen=True)
class Label:
    """One categorical label on a rubric criterion."""

    value: str
    description: str
    score: float


@dataclass(slots=True, frozen=True)
class Criterion:
    """One axis of judgment."""

    name: str
    description: str
    labels: tuple[Label, ...]

    def label_for(self, value: str) -> Label | None:
        for lbl in self.labels:
            if lbl.value == value:
                return lbl
        return None


@dataclass(slots=True, frozen=True)
class Rubric:
    """A complete judge rubric — a tuple of criteria + an optional name."""

    name: str = ""
    criteria: tuple[Criterion, ...] = field(default_factory=tuple)

    def fingerprint(self) -> str:
        """Stable SHA-256 hex of the rubric definition (used in cache keys)."""
        payload = {
            "name": self.name,
            "criteria": [
                {
                    "name": c.name,
                    "description": c.description,
                    "labels": [
                        {"value": lbl.value, "description": lbl.description, "score": lbl.score} for lbl in c.labels
                    ],
                }
                for c in self.criteria
            ],
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def load_rubric(source: str | Path | dict[str, Any] | Rubric) -> Rubric:
    """Load a Rubric from a path, a dict, or pass-through if already a Rubric."""
    if isinstance(source, Rubric):
        return source
    if isinstance(source, dict):
        return _from_dict(source)

    path = Path(source)
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    if suffix in {".yaml", ".yml"}:
        return _from_dict(yaml.safe_load(text) or {})
    if suffix in {".md", ".markdown", ""}:
        return _from_markdown(text)
    raise ValueError(f"Unsupported rubric extension: {suffix!r} (use .md or .yaml).")


def _from_dict(data: dict[str, Any]) -> Rubric:
    name = str(data.get("name", "")).strip()
    raw_criteria = data.get("criteria", [])
    criteria: list[Criterion] = []
    for item in raw_criteria:
        labels = tuple(
            Label(
                value=str(lbl["value"]),
                description=str(lbl.get("description", "")).strip(),
                score=float(lbl.get("score", 0.0)),
            )
            for lbl in item.get("labels", [])
        )
        criteria.append(
            Criterion(
                name=str(item["name"]).strip(),
                description=str(item.get("description", "")).strip(),
                labels=labels,
            )
        )
    return Rubric(name=name, criteria=tuple(criteria))


# Markdown parser — intentionally tiny: header, sections per `##`, bullet
# labels matching `- value [score]: description`.
_LABEL_RE = re.compile(
    r"^\s*[-*]\s*(?P<value>[A-Za-z0-9_+-]+)\s*\[(?P<score>[0-9]*\.?[0-9]+)\]\s*:?\s*(?P<desc>.*?)\s*$"
)


def _from_markdown(text: str) -> Rubric:
    lines = text.splitlines()
    name = ""
    criteria: list[Criterion] = []
    cur_name: str | None = None
    cur_desc: list[str] = []
    cur_labels: list[Label] = []

    def _flush() -> None:
        if cur_name is None:
            return
        criteria.append(
            Criterion(
                name=cur_name,
                description=" ".join(cur_desc).strip(),
                labels=tuple(cur_labels),
            )
        )

    for raw in lines:
        line = raw.rstrip()
        if line.startswith("# "):
            # `# Rubric: Foo` or just `# Foo`
            header = line[2:].strip()
            if header.lower().startswith("rubric"):
                _, _, after = header.partition(":")
                name = (after or header).strip()
            else:
                name = header
            continue
        if line.startswith("## "):
            _flush()
            cur_name = line[3:].strip()
            cur_desc = []
            cur_labels = []
            continue
        if cur_name is None:
            continue
        match = _LABEL_RE.match(line)
        if match:
            cur_labels.append(
                Label(
                    value=match["value"],
                    description=match["desc"].strip(),
                    score=float(match["score"]),
                )
            )
        elif line.strip():
            cur_desc.append(line.strip())

    _flush()
    return Rubric(name=name, criteria=tuple(criteria))


# ---------------------------------------------------------------------------
# Prompt formatter
# ---------------------------------------------------------------------------


_PROMPT_TEMPLATE = """You are an impartial classification judge. For each criterion below, choose
exactly one label from the allowed list. Reason briefly first, then output a
single JSON object on the LAST line of your response.

Rubric: {rubric_name}

{criteria_block}

{reference_block}Response under evaluation:
\"\"\"
{response}
\"\"\"

Instructions:
1. Briefly explain your reasoning per criterion (2-3 sentences each).
2. End with a JSON object on its own line: {{{json_schema}}}
3. Use ONLY the listed label values; do not invent new ones.
"""


def format_judge_prompt(
    response: str,
    rubric: Rubric,
    reference: str | None = None,
) -> str:
    """Render the chain-of-thought-then-classify prompt."""
    if not rubric.criteria:
        raise ValueError("Cannot format a judge prompt for a rubric with no criteria.")

    blocks: list[str] = []
    schema_parts: list[str] = []
    for c in rubric.criteria:
        labels_md = "\n".join(f"  - `{lbl.value}` (score {lbl.score:g}): {lbl.description}" for lbl in c.labels)
        blocks.append(f"### {c.name}\n{c.description or '(no description)'}\nAllowed labels:\n{labels_md}")
        allowed = " | ".join(f'"{lbl.value}"' for lbl in c.labels)
        schema_parts.append(f'"{c.name}": <{allowed}>')

    reference_block = ""
    if reference is not None:
        reference_block = f'Reference (ground-truth) answer:\n"""\n{reference}\n"""\n\n'

    return _PROMPT_TEMPLATE.format(
        rubric_name=rubric.name or "(unnamed)",
        criteria_block="\n\n".join(blocks),
        reference_block=reference_block,
        response=response,
        json_schema=", ".join(schema_parts),
    )


def parse_judge_response(text: str, rubric: Rubric) -> dict[str, str]:
    """Best-effort: pull the trailing JSON object out of a judge response.

    Tolerant of trailing whitespace and code-fences. Falls back to scanning
    every JSON-looking object in the text and picking the last one whose keys
    are a subset of the rubric criterion names.
    """
    criterion_names = {c.name for c in rubric.criteria}
    candidates: list[dict[str, str]] = []
    for match in re.finditer(r"\{[^{}]*\}", text, flags=re.DOTALL):
        try:
            obj = json.loads(match.group(0))
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and set(obj.keys()) & criterion_names:
            candidates.append({str(k): str(v) for k, v in obj.items()})
    if not candidates:
        raise ValueError("No JSON object matching the rubric criteria found in judge response.")
    return candidates[-1]
