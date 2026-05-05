"""AgentCard JSON ↔ dataclass conversion helpers (ADR-008).

Kept in a separate module so :mod:`AgentGuard.subagents.types` stays small
enough to fit the 300-line ceiling. Imported lazily by ``types.py`` only
when needed (well-known/agent.json round-trips).
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from AgentGuard.subagents.types import (
    AgentCapabilities,
    AgentCard,
    AgentInterface,
    AgentProvider,
    AgentSkill,
)

_KNOWN_CARD_KEYS = frozenset(
    {
        "name",
        "description",
        "version",
        "url",
        "capabilities",
        "skills",
        "default_input_modes",
        "default_output_modes",
        "provider",
        "supported_interfaces",
        "documentation_url",
        "icon_url",
    }
)


def card_from_dict(raw: dict[str, Any]) -> AgentCard:
    """Build an :class:`AgentCard` from raw JSON (well-known/agent.json shape)."""
    cap_raw = raw.get("capabilities", {}) or {}
    capabilities = AgentCapabilities(
        streaming=bool(cap_raw.get("streaming", False)),
        push_notifications=bool(cap_raw.get("push_notifications", False)),
        extended_agent_card=bool(cap_raw.get("extended_agent_card", False)),
    )
    skills = tuple(
        AgentSkill(
            id=str(s.get("id", "")),
            name=str(s.get("name", "")),
            description=str(s.get("description", "")),
            tags=tuple(s.get("tags", []) or []),
            examples=tuple(s.get("examples", []) or []),
        )
        for s in raw.get("skills", []) or []
    )
    interfaces = tuple(
        AgentInterface(
            url=str(i.get("url", "")),
            protocol_binding=str(i.get("protocol_binding", "jsonrpc")),
            protocol_version=str(i.get("protocol_version", "1.0")),
            tenant=str(i.get("tenant", "")),
        )
        for i in raw.get("supported_interfaces", []) or []
    )
    provider_raw = raw.get("provider")
    provider = (
        AgentProvider(
            organization=str(provider_raw.get("organization", "")),
            url=str(provider_raw.get("url", "")),
        )
        if isinstance(provider_raw, dict)
        else None
    )
    extras = {k: v for k, v in raw.items() if k not in _KNOWN_CARD_KEYS}
    return AgentCard(
        name=str(raw.get("name", "")),
        description=str(raw.get("description", "")),
        version=str(raw.get("version", "1.0")),
        url=str(raw.get("url", "")),
        capabilities=capabilities,
        skills=skills,
        default_input_modes=tuple(raw.get("default_input_modes", []) or []),
        default_output_modes=tuple(raw.get("default_output_modes", []) or []),
        provider=provider,
        supported_interfaces=interfaces,
        documentation_url=str(raw.get("documentation_url", "")),
        icon_url=str(raw.get("icon_url", "")),
        extras=extras,
    )


def card_to_dict(card: AgentCard) -> dict[str, Any]:
    """Render an :class:`AgentCard` as a JSON-ready dict (A2A 1.0 wire shape)."""
    out: dict[str, Any] = {
        "name": card.name,
        "description": card.description,
        "version": card.version,
        "default_input_modes": list(card.default_input_modes),
        "default_output_modes": list(card.default_output_modes),
        "capabilities": asdict(card.capabilities),
        "skills": [asdict(s) | {"tags": list(s.tags), "examples": list(s.examples)} for s in card.skills],
        "supported_interfaces": [asdict(i) for i in card.supported_interfaces],
    }
    if card.url:
        out["url"] = card.url
    if card.provider:
        out["provider"] = asdict(card.provider)
    if card.documentation_url:
        out["documentation_url"] = card.documentation_url
    if card.icon_url:
        out["icon_url"] = card.icon_url
    if card.extras:
        out.update(card.extras)
    return out


def card_to_json(card: AgentCard, *, indent: int | None = None) -> str:
    """Serialise an :class:`AgentCard` to JSON (well-known/agent.json shape)."""
    return json.dumps(card_to_dict(card), indent=indent, sort_keys=True)


__all__ = [
    "card_from_dict",
    "card_to_dict",
    "card_to_json",
]
