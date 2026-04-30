"""Experiment 08: A2A protocol has a Python SDK on PyPI (research §2.4).

Assumption: a2a-sdk (or python-a2a) exists on PyPI mature enough to wrap as
the SubAgents/A2ALibrary backbone.
"""
import json
import subprocess
import sys
import urllib.request


def pypi_info(pkg: str):
    try:
        with urllib.request.urlopen(f"https://pypi.org/pypi/{pkg}/json", timeout=15) as r:
            return json.load(r)
    except Exception as e:
        return {"_error": f"{type(e).__name__}: {e}"}


def main() -> int:
    found = []
    for pkg in ("a2a-sdk", "python-a2a"):
        info = pypi_info(pkg)
        if "_error" in info:
            print(f"{pkg}: {info['_error']}")
            continue
        meta = info.get("info", {})
        print(f"--- {pkg} ---")
        print("  version :", meta.get("version"))
        print("  summary :", meta.get("summary"))
        print("  requires:", meta.get("requires_python"))
        print("  home    :", meta.get("home_page") or meta.get("project_urls", {}))
        rels = list((info.get("releases") or {}).keys())
        print(f"  releases: {len(rels)} versions, latest 3 = {rels[-3:] if rels else []}")
        found.append((pkg, meta.get("version")))

    ok = bool(found)
    print("PASS" if ok else "FAIL", "exp_08_a2a_python_sdk", "found=", found)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
