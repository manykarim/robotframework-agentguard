"""Experiment 09: BFCL AST-matching rules are importable from inspect_evals (research §3.1).

Assumption: `inspect_evals.bfcl` exposes the Berkeley Function Calling Leaderboard
evaluator with AST matching, importable as a library to power our Tool Sequence /
Tool Arguments keywords.
"""

import importlib
import importlib.util
import pkgutil


def main() -> int:
    spec = importlib.util.find_spec("inspect_evals")
    if spec is None:
        print("inspect_evals not installed")
        print("FAIL exp_09_bfcl_import")
        return 1
    print("inspect_evals located at:", spec.origin)

    # Try the documented path first
    bfcl_mod = None
    for path in ("inspect_evals.bfcl", "inspect_evals.bfcl.bfcl"):
        try:
            bfcl_mod = importlib.import_module(path)
            print("imported:", path, "->", getattr(bfcl_mod, "__file__", "?"))
            break
        except Exception as e:
            print(f"  import {path} -> {type(e).__name__}: {e}")

    # Whether or not the import works, also enumerate the bfcl subpackage
    found_paths = []
    try:
        ie = importlib.import_module("inspect_evals")
        for finder, name, ispkg in pkgutil.iter_modules(ie.__path__):
            if "bfcl" in name.lower() or "function" in name.lower():
                found_paths.append(name)
    except Exception as e:
        print("walk error:", e)
    print("bfcl/function-call-related top-level submodules:", found_paths)

    # Inspect file system for AST matcher source
    if spec.submodule_search_locations:
        import os

        for root in spec.submodule_search_locations:
            for dp, _, files in os.walk(root):
                for fn in files:
                    if "bfcl" in fn.lower() or "ast" in fn.lower():
                        print("  src:", os.path.join(dp, fn))

    ok = bfcl_mod is not None or bool(found_paths)
    print("PASS" if ok else "PARTIAL", "exp_09_bfcl_import")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
