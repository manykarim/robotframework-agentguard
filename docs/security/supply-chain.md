# Supply-Chain Controls — for AgentGuard Itself

The library scans *other people's* skills (`skill-scanner-spec.md`) and isolates *other
people's* code (`sandbox-spec.md`). This document covers the parallel obligation: keeping
**AgentGuard's own** distribution trustworthy. Maps to NIST SSDF (SP 800-218), SLSA v1.0
build levels, and the threat surfaces from `threat-model.md`.

## 1. SBOM generation

| Format | Tooling | When |
|---|---|---|
| `requirements.txt` (pip-style, with hashes) | `uv export --format requirements-txt --hashes` | Every CI build, attached to release |
| **CycloneDX 1.5** JSON | `cyclonedx-py environment` (CycloneDX Python plugin) | Every release tag |
| SPDX 2.3 JSON | optional, via `cyclonedx-py … --output-format spdx-json` | On request (govt / enterprise) |

SBOM is published as a GitHub Release artifact alongside the wheel + sdist and signed (§5).
Mitigates *opaque dependency risk* (CWE-1357) and aligns with NIST SP 800-218 PW.4.4.

## 2. Pinned + hashed dependencies (`uv.lock`)

- `uv.lock` is committed and is the single source of truth for resolved versions.
- Lockfile pins **transitive** deps with sha256 hashes (default `uv` behaviour).
- CI runs `uv sync --locked --frozen`; any drift fails the build (CWE-1104).
- Renovate / Dependabot PRs are required to regenerate `uv.lock` and re-run the
  vulnerability scan (§4) before merge.
- Allowed install index: PyPI only (no custom indexes); enforced via
  `tool.uv.index-url = "https://pypi.org/simple"` and `--no-allow-index-overrides`
  in CI.

## 3. Reproducible builds

AgentGuard produces deterministic wheels / sdists by:

- pinning `SOURCE_DATE_EPOCH` to the commit timestamp;
- running `uv build --no-sources` in a clean container with a pinned `python` digest
  and pinned `uv` digest;
- normalising file permissions and zip ordering;
- publishing the build environment recipe (Dockerfile + digest) alongside the SBOM.

A reviewer with the same source commit + recipe MUST be able to reproduce identical
sha256s for `agentguard-X.Y.Z-py3-none-any.whl`. This is the SLSA L3 *isolated, parameterless,
hermetic* build property.

## 4. Vulnerability scanning

| Layer | Tool | Failure mode |
|---|---|---|
| Python deps | `pip-audit` against PyPA Advisory DB (`uv pip audit` does not yet exist as a first-class subcommand — **gap noted**, tracked separately) | CI fails on any `HIGH`/`CRITICAL` advisory |
| Container base images | `trivy image` against the build & sandbox base images | CI fails on `CRITICAL`; warns on `HIGH` |
| Secrets in source | `gitleaks` pre-commit + CI | Blocks on any finding |
| License compliance | `pip-licenses` + allowlist (`MIT`, `BSD-*`, `Apache-2.0`, `MPL-2.0`, `ISC`, `PSF-2.0`) | CI fails on copyleft (`GPL-*`) leaking into runtime deps |

The `pip-audit` gap is intentionally surfaced — research §8 anticipates supply-chain
incidents (`ToxicSkills`, `ClawHavoc`); the harness's own deps must not become the next
data point.

## 5. Cosign-signed PyPI releases

Per PEP 740 / PyPI Trusted Publishers + Sigstore:

- Releases are built only via the `release.yml` GitHub Actions workflow (OIDC → PyPI
  Trusted Publisher), no long-lived API tokens (CWE-798).
- Each artifact (`*.whl`, `*.tar.gz`, `sbom-cdx.json`) is signed with `cosign sign-blob`
  using GitHub OIDC; signatures published as PyPI **attestations** (PEP 740).
- Reproducible-build verification (§3) is a release-job pre-condition.
- The release manager runs `cosign verify-blob` against a clean checkout before announcing.

Consumers verify via `pip install agentguard --require-hashes` plus the published
attestation; an organisation policy check can require attestations via `pip install
--require-attestations` (Python 3.13+ / pip 25+).

## 6. Hash-verified Inspect AI eval datasets

The harness ships *references* to public eval datasets (BFCL, GAIA, SWE-bench Verified,
HumanEval, MBPP, LiveCodeBench, Aider — research §2.5). Each reference includes:

- canonical URL,
- pinned commit SHA / release tag,
- sha256 of the downloaded archive (verified at download time),
- license note.

The dataset loader (`agentguard.datasets.fetch`) **refuses to load** if the sha256 does
not match the pin (CWE-494, CWE-829). Mitigates the SWE-bench solution-leakage class of
issues (research §2.5 — Yang et al. *SWE-Bench+*) by ensuring users evaluate against the
*Verified* subset they think they're using.

Dataset-pin updates require: (a) a PR that updates the sha256 with rationale,
(b) a re-run of the harness's own canary suite to confirm metrics did not silently shift,
(c) two-reviewer approval. Mirrors research §8.6 (vendor-side regression discipline).

## 7. Release checklist (security gates)

Before a tag is pushed:

1. `uv sync --locked --frozen` clean.
2. `pip-audit` clean (or documented exception with CVE + remediation date).
3. `gitleaks detect --no-banner` clean.
4. `cyclonedx-py environment` produces SBOM; SBOM diff vs previous release attached to
   the release notes.
5. Reproducible-build recipe yields identical wheel sha256 across two runners.
6. Cosign signature + PEP-740 attestation generated.
7. Threat-model and policy-defaults docs reviewed for any new attack surface introduced
   by added deps.

A failed gate blocks the release; downgraded gates (e.g. accepted CVE) require a documented
exception in `docs/security/exceptions.md` (created lazily, on first exception).
