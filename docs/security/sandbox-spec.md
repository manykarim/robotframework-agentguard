# Sandbox Backends — Specification

Implements ADR-013 and the code-execution mandate from `policy-defaults.md` §2. Aligns with
Inspect AI's sandbox plugin interface (research §4.1, §4.4) so the harness can offload to
the same Docker/K8s/Proxmox runners AISI uses.

## 1. Required capabilities (every backend must satisfy)

| Capability | Requirement | Threat addressed (`threat-model.md`) | CWE / Source |
|---|---|---|---|
| **Filesystem isolation** | Read-only root; only the configured workspace bind-mount is RW; no host `/var/run/docker.sock`, `/proc/1/root`, or `/sys` access | 1.I, 4.T, 4.E | CVE-2024-21626 (*Leaky Vessels*); CWE-22 |
| **Network egress control** | Default deny-all; explicit per-test allowlist (host:port) only | 1.I, 4.I (ClawHavoc / AMOS exfiltration) | CWE-918 |
| **CPU / memory / PID caps** | Hard limits enforced by kernel/cgroups (default 1 vCPU, 512 MiB, 256 PIDs) | 1.D, 4.D | CWE-400, CWE-770 |
| **Time bounds** | Wall-clock kill at 5 min default; SIGTERM-then-SIGKILL with 5 s grace | 1.D, 4.D, 5.D | CWE-400 |
| **Privilege drop** | `--cap-drop=ALL`, `--security-opt=no-new-privileges`, non-root UID, user-namespace remap when supported | 4.E | CWE-269, CWE-250 |
| **Determinism** | UTC clock; seeded `/dev/urandom` mode optional; fixed locale `C.UTF-8` | n/a (test reproducibility) | research §2.7 |
| **MCP tool allowlist** | Only the explicit list in §3 may be invoked from inside the sandbox | 2.T, 2.E | OWASP LLM06 |
| **Egress audit** | Every outbound packet logged via cgroup-net or sidecar tcpdump, attached to trajectory | 4.I | CWE-778 |

A backend that cannot satisfy a row above is **not eligible** as a default; it may still
ship as `dev-only` with the unsafe-banner from `policy-defaults.md` §2.

## 2. Backend matrix

| Backend | Status | FS isolation | Net egress control | CPU/Mem caps | Privilege drop | Notes / mapping to Inspect AI |
|---|---|---|---|---|---|---|
| **Docker** *(default)* | Production | bind-mounts; `--read-only` root + tmpfs | `--network=none` or per-test bridge w/ iptables allowlist | `--cpus`, `--memory`, `--pids-limit` | `--cap-drop=ALL`, `--security-opt`, rootless preferred | Maps to Inspect's `docker` sandbox plugin (research §4.1). Pin image by digest. |
| **Kubernetes (pod-per-sample)** | Production | `readOnlyRootFilesystem: true` + emptyDir; no `hostPath` | `NetworkPolicy` egress allowlist; default-deny namespace | `resources.limits` cpu/memory; `pids.max` via runtime | `securityContext: {runAsNonRoot, allowPrivilegeEscalation:false, capabilities.drop:[ALL], seccompProfile: RuntimeDefault}` | Inspect AI Phase-4 plugin; suitable for parallel BFCL/SWE-bench sweeps |
| **Proxmox (LXC/VM)** | Production | Per-CT root w/ AppArmor `lxc-container-default-restricted`; or full VM | Bridged with firewall rules (`pve-firewall`) | LXC `cores`, `memory`, `swap` limits | Unprivileged container; `nesting=0`, `keyctl=0` | Matches AISI Inspect deployment pattern (research §4.1) for high-isolation eval clusters |
| **Process** *(dev-only, INSECURE)* | Dev | `chroot`+`unshare` best-effort; not enforced | None (host network) | `setrlimit` only | `setuid` to nobody if available | Banner: `SANDBOX=process — UNSAFE FOR UNTRUSTED CODE`. Disabled in CI by default. |

Backend selection: `--sandbox=docker|k8s|proxmox|process`; default `docker`. The harness
auto-detects backend availability at startup and refuses to run code-execution keywords if
none of the production backends is configured (fails closed).

## 3. MCP tool allowlist inside the sandbox

A coding agent or skill running inside the sandbox may invoke **only** these MCP tools.
Anything else is rejected by the in-sandbox MCP proxy with `tool_blocked_by_policy`.

| Tool | Why it's allowed |
|---|---|
| `filesystem.read` / `filesystem.write` (workspace-scoped) | The whole point of code-execution tests |
| `bash` / `python` / `text-edit` (Inspect built-ins, research §2.2) | Required for SWE-bench / Aider runs |
| `web_search` (read-only, via library-controlled proxy) | Allowed only when `--allow-egress` includes the search backend |
| `agentguard.judge` (LLM-as-Judge over a redacted candidate) | Returns scalar verdict, not free text into the agent |

Explicitly **denied** (require lifting via `--mcp-tool-allow=name` per-test):
`web_browser` (rich content + click), `computer` (full desktop), arbitrary user-defined
MCP tools, anything talking to a non-loopback URL.

## 4. Inspect AI plugin mapping

The harness implements Inspect AI's sandbox plugin interface (`inspect_ai.util.SandboxEnvironment`):

- `exec(cmd, ...)` → backend-specific exec (docker exec / kubectl exec / pct exec / subprocess).
- `read_file` / `write_file` → workspace-scoped, path-validated against traversal (CWE-22).
- `connection()` → returns blocked unless allowlisted.

This guarantees that any Inspect AI Task/Solver/Scorer reused by the harness (research §4.1)
runs under identical isolation guarantees, satisfying the *integrate, don't reinvent*
principle from research §1.

## 5. Audit trail

Every sandbox lifecycle event (`create`, `exec`, `network_attempt`, `kill`, `destroy`) is
appended to the session JSONL (`policy-defaults.md` §6) with the sha256-chain. Image digest,
backend version, and applied profile name are recorded at `create` time so a report can be
re-validated months later (CWE-778 mitigation).
