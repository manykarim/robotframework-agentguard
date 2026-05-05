"""AgentCard parsing + schema validation helpers (ADR-008).

Used by ``Validate Agent Card`` and ``Get Agent Card``. The A2A 1.0 spec
ships a JSON Schema for ``AgentCard`` but the dataclass-based check we
do here is the same one ``a2a-sdk``'s :class:`A2ACardResolver` performs
internally (mandatory fields + skill shape) — sufficient to catch every
malformed card we have seen in research §6.4.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from AgentGuard.subagents.exceptions import AgentCardInvalid
from AgentGuard.subagents.types import AgentCard, from_dict_card


def parse_card_input(card: dict[str, Any] | str | Path) -> AgentCard:
    """Coerce ``card`` (dict / JSON string / path / file path string) to :class:`AgentCard`."""
    if isinstance(card, Path):
        try:
            raw = json.loads(card.read_text())
        except OSError as exc:
            raise AgentCardInvalid(f"could not read agent card file {card}: {exc}") from exc
        except json.JSONDecodeError as exc:
            raise AgentCardInvalid(f"agent card file {card} is not valid JSON: {exc}") from exc
    elif isinstance(card, str):
        stripped = card.strip()
        if stripped.startswith("{"):
            try:
                raw = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise AgentCardInvalid(f"agent card string is not valid JSON: {exc}") from exc
        else:
            path = Path(stripped)
            if not path.exists():
                raise AgentCardInvalid(f"agent card input is neither JSON nor an existing file: {card!r}")
            try:
                raw = json.loads(path.read_text())
            except json.JSONDecodeError as exc:
                raise AgentCardInvalid(f"agent card file {path} is not valid JSON: {exc}") from exc
    elif isinstance(card, dict):
        raw = card
    else:
        raise AgentCardInvalid(f"unsupported agent card input type: {type(card).__name__}")

    if not isinstance(raw, dict):
        raise AgentCardInvalid(f"agent card root must be an object, got {type(raw).__name__}")
    return from_dict_card(raw)


def assert_card_required_fields(card: AgentCard) -> None:
    """Validate the A2A 1.0 mandatory fields on an :class:`AgentCard`."""
    missing: list[str] = []
    if not card.name:
        missing.append("name")
    if not card.version:
        missing.append("version")
    # A2A 1.0: must declare a top-level url OR at least one supported_interface.
    if not card.url and not card.supported_interfaces:
        missing.append("url|supported_interfaces")
    if missing:
        raise AgentCardInvalid(f"AgentCard missing required field(s): {', '.join(missing)}")
    for i, skill in enumerate(card.skills):
        if not skill.id or not skill.name:
            raise AgentCardInvalid(
                f"AgentCard skill[{i}] is missing id or name (got id={skill.id!r}, name={skill.name!r})"
            )


__all__ = [
    "assert_card_required_fields",
    "parse_card_input",
]
