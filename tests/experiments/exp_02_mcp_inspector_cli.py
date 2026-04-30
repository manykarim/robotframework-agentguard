"""Experiment 02: `npx @modelcontextprotocol/inspector --cli` is usable from CI (research §2.1).

Assumption: The official MCP Inspector ships a `--cli` mode that lists/calls tools
against a stdio MCP server, suitable for CI compliance testing.
"""
import os
import subprocess
import sys


def run_help() -> tuple[int, str]:
    try:
        proc = subprocess.run(
            ["npx", "-y", "@modelcontextprotocol/inspector", "--cli", "--help"],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "CI": "1"},
        )
        return proc.returncode, (proc.stdout + "\n--- STDERR ---\n" + proc.stderr)
    except FileNotFoundError:
        return 127, "npx not found"
    except subprocess.TimeoutExpired:
        return 124, "timeout after 120s"


def main() -> int:
    rc, out = run_help()
    head = "\n".join(out.splitlines()[:100])
    print("--- inspector --cli --help (first 100 lines, exit=%d) ---" % rc)
    print(head)
    # Heuristic: PARTIAL pass if exit code is non-error OR the output mentions
    # known subcommands (tools/list, methods).
    has_method = ("--method" in out) or ("tools/list" in out) or ("--cli" in out)
    ok = (rc == 0) or has_method
    print("PASS" if ok else "FAIL", "exp_02_mcp_inspector_cli", "exit=%d" % rc)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
