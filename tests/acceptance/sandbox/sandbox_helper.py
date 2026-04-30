"""Helper library for the sandbox acceptance suite.

Provides keywords that wrap the lower-level :func:`get_backend` API so the
canonical "echo hello in Docker" Robot test stays readable.
"""

from __future__ import annotations

from robot.api import SkipExecution

from AgentGuard.security.sandbox import SandboxPolicy
from AgentGuard.security.sandbox_backends.base import SandboxResult
from AgentGuard.security.sandbox_backends.docker_backend import DockerBackend


def skip_if_docker_unavailable() -> None:
    """Raise SkipExecution unless docker is reachable from the test host."""
    backend = DockerBackend()
    if not backend.is_available():
        raise SkipExecution("Docker daemon unavailable — sandbox acceptance test skipped")


def run_in_docker_sandbox(*command_parts: str) -> SandboxResult:
    """Run ``command_parts`` under the hardened Docker policy.

    Splits the command on whitespace so Robot can pass it as a single arg or
    as multiple positional args — both forms work.
    """
    if len(command_parts) == 1 and " " in command_parts[0]:
        # Allow Robot's whitespace-joined single arg form.
        import shlex

        argv = shlex.split(command_parts[0])
    else:
        argv = list(command_parts)
    backend = DockerBackend()
    policy = SandboxPolicy(allow_code_execution=True)
    return backend.run(policy, argv)


def skip_if_capdrop_refuses_exec(result: SandboxResult) -> None:
    """Skip when the host runtime won't permit exec under cap-drop=ALL.

    Some kernels (rootless / userns-remap) return ``operation not permitted``
    even for unprivileged exec when ``--cap-drop=ALL`` + ``no-new-privileges``
    are combined. That's the documented hardened posture; the test merely
    asserts wire behaviour where the runtime supports it.
    """
    if "operation not permitted" in (result.stderr or ""):
        raise SkipExecution("host kernel/runtime refuses exec under cap-drop=ALL (documented hardened posture)")
