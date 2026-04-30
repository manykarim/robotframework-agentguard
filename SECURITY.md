# Security Policy

## Reporting a Vulnerability

**Please do NOT open a public issue for a security vulnerability.**

Email the maintainers privately:

- **security@agentguard.dev** (preferred)
- Or open a [GitHub Security Advisory](https://github.com/manykarim/robotframework-agentguard/security/advisories/new)

Include:

1. A description of the issue.
2. Steps to reproduce (minimal Robot/pytest snippet preferred).
3. AgentGuard version (`uv run agentguard version`) and environment.
4. Suggested mitigation, if any.

We aim to acknowledge within **3 business days** and to publish a fix or
mitigation within **30 days** for confirmed High/Critical issues.

## Disclosure timeline

| Step                            | Target |
|---------------------------------|--------|
| Acknowledge report              | 3 days |
| Triage + severity assessment    | 7 days |
| Patch + private review          | 21 days |
| Public advisory + release       | 30 days |

We will credit reporters in the advisory unless they prefer otherwise.

## In scope

- The `AgentGuard` library and CLI.
- Generated libdoc HTML.
- The default-deny **skill scanner** pipeline (ADR-006, ADR-020).
- The **sandbox policy** (ADR-013) and the `--allow-code-execution` opt-in.
- Any `.github/workflows/` shipped in this repo.

## Out of scope

- Vulnerabilities in upstream dependencies (LiteLLM, FastMCP, Inspect AI,
  scipy, …) — please report those upstream. We will mirror an advisory here
  if a transitive fix requires action by AgentGuard users.
- Third-party Skills / MCP servers that an end user installs into their own
  project.
- Issues that require an attacker to already have a valid Anthropic /
  OpenRouter / OpenAI API key.

## Threat model

The full threat model lives in
[`docs/security/threat-model.md`](docs/security/threat-model.md). Highlights:

| # | Threat                                                   | Mitigation             |
|---|----------------------------------------------------------|------------------------|
| 1 | Skill prompt-injection escalating to host-agent EoP       | ADR-006 default-deny + ADR-020 AIDefence scan |
| 2 | Sandbox escape during code execution                      | ADR-013 Docker profile + `--allow-code-execution` flag |
| 3 | MCP tool-description injection / rug-pull                 | Recording transport, capability snapshot diffs |
| 4 | Hook HTTP exfiltration of `transcript_path`               | Universal redactor + recording HTTP-hook proxy |
| 5 | Skill `scripts/` infostealer (ClawHavoc / AMOS)            | Default-deny scanner pipeline (7 stages) |

## Supply chain

- All releases are built from a tag on `main` via `.github/workflows/release.yml`.
- The `uv.lock` is committed and audited weekly via the
  `.github/workflows/security.yml` schedule (CycloneDX SBOM + `pip-audit`).
- Phase-1 GA target: PyPI Trusted Publishing (no API token in repo secrets)
  and cosign-signed release artifacts. See
  [`docs/security/supply-chain.md`](docs/security/supply-chain.md).

## Hall of fame

To be filled out after the first responsible disclosure. Reporters may opt-out
of attribution.
