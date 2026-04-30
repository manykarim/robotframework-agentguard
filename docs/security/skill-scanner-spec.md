# `Skill Should Pass Security Scan` — Keyword Specification

Formal contract for the security gate referenced in `policy-defaults.md` §1 and Phase-4 of
the implementation plan (`docs/research/research.md` §5 Phase 4). Implements the
default-deny posture mandated by ADR-006.

## 1. Signature

```robotframework
Skill Should Pass Security Scan
...    skill=path|object       # required: filesystem path OR loaded SkillObject
...    severity_threshold=CRITICAL    # CRITICAL | HIGH | MEDIUM | INFO
...    require_signature=True
...    marketplace_allowlist=@{NONE}
...    judge_model=${NONE}            # used only for ambiguous prompt-injection cases
```

Returns: `${SkillSecurityReport}` (see §3). Raises `SkillSecurityError` when the report's
`decision == "deny"`.

## 2. Pipeline (sequential, fail-fast on CRITICAL)

| # | Stage | Tool | CWE / Source | Failure severity |
|---|---|---|---|---|
| 1 | **Frontmatter validation** | YAML parse + JSON-schema (`name`, `description`, optional `allowed-tools`) per Agent Skills spec (research §2.2) | CWE-20 | CRITICAL on invalid YAML; HIGH on missing required keys |
| 2 | **`allowed-tools` whitelist** | Compare frontmatter against the harness-configured tool allowlist; cross-check that referenced MCP server URLs match the suite's pinned set | CWE-285, OWASP LLM06 | HIGH when an unknown tool requested; CRITICAL when a denylisted tool requested (e.g. `Bash` without `--allow-code-execution`) |
| 3 | **Static analysis of `scripts/`** | Regex pack + Bandit ruleset; checks for `curl ... \| sh`, `eval`, `exec`, `pickle.loads`, `subprocess(*, shell=True)` with interpolation, raw `os.system`, `__import__("..."+x)` | CWE-78, CWE-94, CWE-502, CWE-95 | CRITICAL on shell-injection-shaped patterns; HIGH on `eval`/`exec` of static strings; MEDIUM on `subprocess` without `shell=True` but unpinned binary path |
| 4 | **AIDefence prompt-injection scan** | `aidefence_scan` invoked on `SKILL.md` body (post-frontmatter) and **every** `references/*.md` and any `.md` under the skill folder | OWASP LLM01, CWE-1427 | Severity mirrors AIDefence verdict (CRITICAL/HIGH/MEDIUM/INFO) |
| 5 | **Signature verification** | (a) Cosign / Sigstore-style detached signature `SKILL.md.sig` against a configured trust root, **or** (b) Anthropic-issued JWT in `skill.signature` frontmatter field, validated against the publisher's JWKS | CWE-347 | CRITICAL when `require_signature=True` and verification fails; HIGH when signature present but expired |
| 6 | **Marketplace reputation** | Skill `name` + publisher checked against `marketplace_allowlist`; cross-checked against an optional denylist file shipped with AgentGuard releases (publishers known from *ToxicSkills*, *ClawHavoc*) | CWE-829 | CRITICAL on denylist hit; HIGH when publisher unknown and `marketplace_allowlist` is non-empty (allowlist mode) |
| 7 | **PII / secret scan** | `aidefence_has_pii` over the whole folder; high-entropy regex pack from `policy-defaults.md` §5 | CWE-540, CWE-798 | CRITICAL on detected live credential; HIGH on PII; INFO on placeholder material |

Stages 1–2 run in-process, stage 3 in a subprocess with no network, stages 4 & 7 via the
RuFlo MCP tools (`mcp__claude-flow__aidefence_scan`, `…_has_pii`), stage 5 via `cosign verify-blob`
or PyJWT, stage 6 via in-memory file lookup. Stage ordering is intentional: cheap checks
gate expensive ones (CWE-754).

## 3. Output schema (`SkillSecurityReport`)

```python
@dataclass(frozen=True)
class SkillSecurityFinding:
    stage: str                 # "frontmatter" | "allowed_tools" | "scripts_static" | …
    severity: Literal["CRITICAL", "HIGH", "MEDIUM", "INFO"]
    rule_id: str               # e.g. "AGRD-S-101"
    cwe: list[str]             # e.g. ["CWE-78", "CWE-94"]
    location: str              # "scripts/install.sh:L42" | "SKILL.md:body" | "frontmatter:allowed-tools[3]"
    message: str
    remediation: str           # actionable hint, never `eval`-able

@dataclass(frozen=True)
class SkillSecurityReport:
    skill_path: Path
    skill_name: str
    publisher: str | None
    signature_status: Literal["valid", "invalid", "missing", "expired", "untrusted_root"]
    findings: list[SkillSecurityFinding]
    counts: dict[Literal["CRITICAL","HIGH","MEDIUM","INFO"], int]
    decision: Literal["allow", "warn", "deny"]
    decision_reason: str
    scanned_at: datetime         # UTC, monotonic-fenced
    scanner_version: str
    policy_sha256: str           # hash of the active policy file
```

## 4. Decision matrix (default policy)

| Condition | `decision` |
|---|---|
| Any CRITICAL finding | `deny` |
| `signature_status in {"missing","invalid","untrusted_root"}` AND publisher ∉ first-party | `deny` |
| Any HIGH finding AND no CRITICAL | `warn` (passes if `--allow-suspicious-skill`) |
| Only MEDIUM / INFO findings | `allow` |
| No findings | `allow` |

`severity_threshold` parameter raises the bar: e.g. `severity_threshold=HIGH` treats HIGH
as `deny` for stricter CI gates. It can never *lower* the bar below CRITICAL.

## 5. Determinism guarantees

- All regex packs are versioned (`AGRD-S-XXX` rule IDs); the policy file's sha256 is
  embedded in the report so two runs against the same policy must yield identical
  `findings` (modulo timestamps).
- AIDefence and JWT verification are external dependencies — their *verdicts* are
  recorded with a `verdict_hash` so flaky upstreams are detectable across runs.

## 6. Performance budget

- Stage 1–3, 5–7: synchronous, target < 200 ms per skill on a 50-file skill.
- Stage 4 (AIDefence): async, parallelised across `references/`, target < 2 s per skill.
- Total wall-clock budget for a 50-skill marketplace scan: ≤ 60 s.

## 7. Out of scope

- **Behavioural execution.** This keyword does *not* run the skill. Behavioural assertions
  belong to `Run Skill Eval` and the LLM-as-Judge path (`policy-defaults.md` §4).
- **Vendor-side regression.** Drift in upstream CLI tools is covered by the canary suite
  (research §8.6), not this keyword.
