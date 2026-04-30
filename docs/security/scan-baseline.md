# Security Scan Baseline

Per the project's `CLAUDE.md` Security Rules, `npx @claude-flow/cli@latest security scan`
was executed after the security docs were authored. This appendix captures the raw output
so subsequent runs have a comparison baseline.

## Run metadata

- Command: `npx @claude-flow/cli@latest security scan`
- Working directory: `/home/many/workspace/robotframework-agentguard`
- Date: 2026-04-29 (UTC)
- Commit: pre-commit (working tree)
- Tool resolved: `@claude-flow/cli@3.6.9` (auto-installed by npx)

## Raw output

```
npm warn exec The following package was not found and will be installed: @claude-flow/cli@3.6.9
npm error code ENOTEMPTY
npm error syscall rename
npm error path /home/many/.npm/_npx/85fb20e3e7e3a233/node_modules/agentic-flow
npm error dest /home/many/.npm/_npx/85fb20e3e7e3a233/node_modules/.agentic-flow-AxKSKWSG
npm error errno -39
npm error ENOTEMPTY: directory not empty, rename
  '/home/many/.npm/_npx/85fb20e3e7e3a233/node_modules/agentic-flow'
  -> '/home/many/.npm/_npx/85fb20e3e7e3a233/node_modules/.agentic-flow-AxKSKWSG'
npm error A complete log of this run can be found in:
  /home/many/.npm/_logs/2026-04-29T18_49_51_034Z-debug-0.log
```

## Interpretation

The scan **did not run**: npx failed to install `@claude-flow/cli@3.6.9` due to an
`ENOTEMPTY` error in `~/.npm/_npx/85fb20e3e7e3a233/node_modules/agentic-flow` — a stale
artifact from a previous concurrent install. This is environmental (CWE-755 in the
operating environment, not in AgentGuard) and not a security finding against the library.

Reproduction steps and remediation:

1. `rm -rf ~/.npm/_npx/85fb20e3e7e3a233` (clears the stale npx cache).
2. Re-run `npx @claude-flow/cli@latest security scan`.
3. If the failure persists, fall back to a project-local install:
   `npm install --no-save @claude-flow/cli@latest && ./node_modules/.bin/claude-flow security scan`.

## Action items

- [ ] Add `npx-cache-clean` to the project's `scripts/` once the `/scripts` directory
  exists (do not create now per CLAUDE.md "no unrequested files").
- [ ] Capture a real baseline scan in CI on the next green build; commit the resulting
  output here as the canonical `## Run metadata` block, replacing this notice.
- [ ] When the actual scan runs clean, append per-finding details (rule ID, severity,
  file:line, CWE) so future runs can `diff` against this baseline.

This file is intentionally checked in *before* a successful scan so the gap is visible
to reviewers; an empty/missing `scan-baseline.md` would silently hide the failure.
