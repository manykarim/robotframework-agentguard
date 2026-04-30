---
name: curl-pipe-skill
description: Skill whose installer script demonstrates the `curl ... | sh` antipattern.
allowed-tools:
  - Bash
publisher: unknown-author
---

# One-Click Installer

Run `scripts/install.sh` to bootstrap the toolchain. The script downloads
and executes a remote installer over HTTPS. This is the exact antipattern
that the static-analysis stage should flag as CRITICAL (CWE-78 / supply-chain
risk).
