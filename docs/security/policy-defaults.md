# AgentGuard Secure-Default Policy

**Principle:** *secure by default, opt-in to risk*. Every default below can be relaxed via an
explicit CLI flag or `*** Settings ***` argument; the relaxed posture is logged in the Robot
HTML report header so reviewers can spot it. Defaults derive from the threat model
(`threat-model.md`) and align with the ADRs being drafted in parallel:
ADR-006 (skill default-deny), ADR-013 (sandbox), ADR-020 (AIDefence integration).

Citations reference `docs/research/research.md` (§X.Y), CWE/OWASP-LLM identifiers, and
external incidents.

---

## §1. Skill Loading — Default-Deny Pipeline

Every skill loaded via `Load Skill` or auto-discovered under `.claude/skills/`,
`.agents/skills/`, `~/.gemini/.../skills/`, `~/.codex/skills/` (research §2.2) passes through:

a. **Prompt-injection scan.** `aidefence_scan` (RuFlo MCP tool, see CLAUDE.md "Security")
   on `SKILL.md` body and every `references/*.md`. CRITICAL verdict → deny;
   HIGH → warn + require `--allow-suspicious-skill`. Mitigates OWASP LLM01 and the
   *ToxicSkills* 36 % flawed rate (research §8.3).

b. **Signature check.** Cosign-style or Anthropic-issued JWT (per `skill-scanner-spec.md`
   stage 5). **Default-deny unsigned third-party skills** (research §8.3); first-party skills
   bundled with the harness are signed by the AgentGuard release key.

c. **Static analysis of `scripts/`.** Regex + Bandit-style AST checks for known suspicious
   patterns: `curl ... | sh`, `wget ... | bash`, `eval(`, `exec(`, `subprocess.*shell=True`
   with f-string interpolation, `os.system`, `__import__`, `pickle.loads`, `requests.get`
   to non-allowlisted hosts. Maps to CWE-78, CWE-94, CWE-502.

d. **PII / credential scan.** `aidefence_has_pii` over the entire skill folder; deny on
   detected secret material being shipped *with* the skill (CWE-540, CWE-798).

e. **MCP tool-description scan.** When a skill's `allowed-tools` references an MCP server,
   the server's `tools/list` descriptions are also scanned (Threat 2.T). Mitigates
   tool-description-injection / *rug-pull*.

**Override:** `--allow-unscanned-skills` disables (a)+(c)+(d)+(e). It cannot disable (b);
unsigned skills require `--allow-unsigned-skills` separately.

---

## §2. Sandbox — Required for Any Code-Execution Keyword

Any keyword that executes agent-generated or skill-supplied code (`Run Coding Agent`,
`Run Skill Script`, `Run Hook Command`, MCP `tools/call` against a tool whose schema
includes `execute_code`) requires **both**:

- explicit `--allow-code-execution` flag (mirrors AISI guidance — research §8.2), and
- a configured sandbox backend per `sandbox-spec.md`.

**Default backend: Docker** with the *minimal* profile:
read-only root filesystem, tmpfs `/tmp` (size-capped), workspace bind-mounted RW, no
network (`--network=none`), no Docker-socket mount, `--cap-drop=ALL`, `--security-opt=no-new-privileges`,
rootless or `--user=$(id -u):$(id -g)`, CPU/mem/PID limits enforced, 5-minute wall-clock cap.

Mitigates CVE-2024-21626 *Leaky Vessels*-class escapes (Threat 4.E) and prevents
*ClawHavoc* AMOS exfiltration (Threat 1.I) by removing network egress.

**Process backend** is provided for local dev only and prints a red banner
`SANDBOX=process — UNSAFE FOR UNTRUSTED CODE`.

---

## §3. Hook Execution — Isolated by Default

Every hook handler runs in a fresh tmpdir under `$TMPDIR/.agentguard/hooks/<run-id>/` with:

- `env={}` (no inheritance) unless `--inherit-env=KEY1,KEY2` allowlist is passed.
  Mitigates Threat 3.I (HTTP hook leaking `OPENAI_API_KEY` from environment).
- `cwd=` the tmpdir, never the project root.
- `transcript_path` redacted via §5 redactor before being made available to the hook.
- HTTP-handler hooks are routed through a built-in **recording proxy** that:
  - logs request URL, headers, body to the test trajectory;
  - blocks any non-allowlisted destination (default allowlist: `127.0.0.1`, `localhost`);
  - rejects responses larger than 1 MiB.
- Wall-clock cap 30 s; exit-code-2 (block) is honoured but the harness asserts
  `Hook Should Block`/`Hook Should Allow` rather than letting it ride silently
  (research §2.3 hook semantics).

---

## §4. LLM-as-Judge — Sanitised Inputs, Strict Output

Per Hamel Husain / Braintrust best practice (research §2.7) and OWASP LLM01:

- Every judge **input** (the candidate output being graded) is `aidefence_scan`'d for
  prompt-injection before submission. CRITICAL → judge refuses to score and the test
  fails closed (`Judge Refused — Prompt Injection`).
- Judge **output** is parsed with a strict JSON schema (`{verdict: "pass"|"fail",
  score: number, rationale: string}`). **Never `eval`** (CWE-95). Schema-mismatch → fail closed.
- Judge model is classification-based, not free-form numeric (research §2.7).
- `Calibrate Judge` keyword (research §8.1) is required to run before any judge-graded
  test in a CI run; Cohen's κ < 0.6 against the human-labelled set blocks the suite.

---

## §5. Secret & PII Redaction

A single redactor (`agentguard.security.redactor`) runs over every tool input, tool output,
hook stdin/stdout, judge prompt, and persisted JSONL line **before** logging. It uses:

- `aidefence_has_pii` for general PII (CWE-359);
- a built-in regex pack for high-entropy strings (CWE-798): AWS keys (`AKIA[0-9A-Z]{16}`),
  GitHub PATs (`ghp_[A-Za-z0-9]{36}`), Anthropic keys (`sk-ant-[A-Za-z0-9-]{32,}`),
  OpenAI keys (`sk-(proj-)?[A-Za-z0-9]{20,}`), JWTs, RSA/EC PEM blocks, `.env`-style
  `KEY=value` lines for known secret KEYs;
- structural redaction of HTTP `Authorization`, `Cookie`, `Set-Cookie` headers.

Redacted values are replaced with `<REDACTED:KIND:sha256[:8]>` so reviewers can correlate
without seeing the secret. Mitigates Threat 2.I, 3.I, 4.I.

---

## §6. Trajectory Storage — Local, Restrictive, Auto-Gitignored

Session JSONL transcripts are written to `<project>/.agentguard/sessions/<session-id>.jsonl`
with:

- file mode `0600`, directory mode `0700` (CWE-732);
- a sha256 chain (`prev_hash` field per line) so tampering is detectable (Threat 4.R);
- monotonic-clock timestamps in addition to wall-clock to detect clock skew;
- `init` keyword auto-appends `.agentguard/` to the project `.gitignore` and warns if a
  prior commit already contains a session file (Threat 4.I — secrets in git history).

Override `--session-dir=` is permitted; the harness still enforces 0600/0700 there.

---

## §7. Network Egress — Allowlist on Test Host

When the harness itself (not the sandbox) needs network — e.g. `Get Agent Card` against an
A2A endpoint — egress goes through an allowlist:

- default allowlist: `127.0.0.1`, `localhost`, `::1`, plus any explicit `agent_url=`
  arguments in the running suite;
- public LLM endpoints (api.anthropic.com, api.openai.com, …) are allowlisted only when
  the corresponding provider is configured;
- `--allow-egress=host[,host...]` widens the list per-suite.

Mitigates Threat 5.I and surfaces unintended outbound calls during test design.

---

## §8. Failure Modes Are Loud

All security defaults **fail closed**. Every default activated, bypassed, or downgraded
during a Robot run is reported in a `SECURITY POSTURE` section at the top of `log.html`,
including the SHA-256 of the active policy file. Mitigates silent vendor-side regressions
(research §8.6, Anthropic April-2026 postmortem).
