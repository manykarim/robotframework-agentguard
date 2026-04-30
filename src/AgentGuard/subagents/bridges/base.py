"""Common contract + helpers for framework bridges (ADR-008).

Each bridge translates a framework's native delegation primitive into the
canonical A2A surface (``AgentCard`` + ``Task``) and a BFCL-shaped trajectory
list ``[{"name": str, "arguments": dict}, ...]`` so the upstream
:class:`AgentGuard.subagents.library.SubAgentsKeywords` can treat all
frameworks uniformly.

Constraints:

* All framework deps are imported lazily *inside* method bodies; the module
  must import cleanly even when the framework is missing so callers can probe
  via :meth:`FrameworkBridge.is_available` and skip.
* Public surface is strictly typed; only the framework-touching internals
  use ``Any`` to avoid leaking optional types into the API.
"""

from __future__ import annotations

import importlib.util
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:  # pragma: no cover - import only for type checkers
    from a2a.types import AgentCard, Task


__all__ = [
    "BridgeUnavailable",
    "FrameworkBridge",
    "find_spec_any",
    "make_agent_card",
    "make_agent_skill",
    "make_task",
]


class BridgeUnavailable(RuntimeError):  # noqa: N818  - "Unavailable" is the canonical name

    """Raised when a bridge method is invoked but its framework is not installed.

    Carries an installation hint suitable for surfacing in Robot Framework
    log output.
    """

    def __init__(self, framework: str, install_hint: str) -> None:
        super().__init__(
            f"{framework} bridge unavailable. Install with: {install_hint}"
        )
        self.framework = framework
        self.install_hint = install_hint


def find_spec_any(*module_names: str) -> bool:
    """Return ``True`` if any of ``module_names`` is importable.

    Used by ``is_available()`` checks to avoid actually importing the
    framework at module-load time.
    """
    for name in module_names:
        try:
            if importlib.util.find_spec(name) is not None:
                return True
        except (ImportError, ValueError):  # pragma: no cover - defensive
            continue
    return False


@runtime_checkable
class FrameworkBridge(Protocol):
    """Protocol every bridge implements.

    All methods are ``@staticmethod`` so bridges can be used without
    instantiation (the registry returns the class itself).
    """

    name: str

    @staticmethod
    def is_available() -> bool:
        """Return ``True`` iff the framework's import is resolvable."""
        ...

    @staticmethod
    def to_agent_card(framework_obj: Any) -> AgentCard:
        """Translate a framework's agent/team object to an A2A ``AgentCard``."""
        ...

    @staticmethod
    def to_task(framework_obj_run_result: Any) -> Task:
        """Translate a framework's run result into an A2A ``Task``."""
        ...

    @staticmethod
    def extract_trajectory(framework_obj_run_result: Any) -> list[dict[str, Any]]:
        """Return a BFCL-shaped trajectory.

        Each entry is ``{"name": <tool_name>, "arguments": <dict>}`` matching
        :func:`AgentGuard.tool_calls.trajectory.normalise_trajectory` input.
        """
        ...

    @staticmethod
    def replay(framework_obj_run_result: Any) -> Any:
        """Return a framework-specific time-travel/replay handle.

        Bridges that don't support replay raise :class:`NotImplementedError`
        with a hint pointing at the framework's own replay API.
        """
        ...


# ---------------------------------------------------------------------------
# A2A type construction helpers
# ---------------------------------------------------------------------------
#
# These are tiny adapters around the a2a-sdk protobuf constructors so each
# bridge body stays focused on framework introspection rather than A2A
# plumbing. ``a2a-sdk`` is a hard dep of the project (see pyproject.toml), so
# importing it at module load is safe.


def make_agent_skill(
    *,
    skill_id: str,
    name: str,
    description: str = "",
    tags: list[str] | None = None,
) -> Any:
    """Build an A2A ``AgentSkill`` with sensible defaults."""
    from a2a.types import AgentSkill

    return AgentSkill(
        id=skill_id,
        name=name,
        description=description,
        tags=list(tags or []),
    )


def make_agent_card(
    *,
    name: str,
    description: str = "",
    version: str = "1.0",
    skills: list[Any] | None = None,
) -> AgentCard:
    """Build a minimal A2A ``AgentCard`` from the canonical fields used by bridges."""
    from a2a.types import AgentCard

    card = AgentCard(
        name=name,
        description=description,
        version=version,
    )
    if skills:
        card.skills.extend(skills)
    return card


def make_task(
    *,
    task_id: str,
    state: Any = None,
    context_id: str = "",
    metadata: dict[str, Any] | None = None,
) -> Task:
    """Build a minimal A2A ``Task`` envelope.

    ``state`` is an ``a2a.types.TaskState`` enum value
    (e.g. ``TaskState.TASK_STATE_COMPLETED``); falls back to
    ``TASK_STATE_UNSPECIFIED`` when not provided. Typed as ``Any`` because the
    proto-generated enum is intentionally not part of the bridge public API.
    """
    from a2a.types import Task, TaskState, TaskStatus
    from google.protobuf.struct_pb2 import Struct

    resolved_state = state if state is not None else TaskState.TASK_STATE_UNSPECIFIED
    task = Task(
        id=task_id,
        context_id=context_id,
        status=TaskStatus(state=resolved_state),
    )
    if metadata:
        struct = Struct()
        # Best-effort: only string-keyed JSON-compatible values can populate
        # a Struct. Anything else is dropped silently — bridges should only
        # pass primitives here.
        try:
            struct.update(metadata)
            task.metadata.CopyFrom(struct)
        except (ValueError, TypeError):  # pragma: no cover - defensive
            pass
    return task
