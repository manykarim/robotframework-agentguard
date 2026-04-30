"""Experiment 05: robotlibcore.DynamicCore composes sub-libraries (research §4.3).

Assumption: A `@library` class extending `DynamicCore` cleanly merges keywords from
multiple sub-library classes. We verify by running a tiny .robot suite end-to-end.
"""
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path


MINILIB_SRC = textwrap.dedent('''
    from robot.api.deco import keyword, library
    from robotlibcore import DynamicCore

    class MathKw:
        @keyword
        def add_numbers(self, a, b):
            return int(a) + int(b)

    class EchoKw:
        @keyword
        def echo_text(self, text):
            return f"echo:{text}"

    @library(scope="SUITE", auto_keywords=False, version="0.0.1")
    class MiniLib(DynamicCore):
        def __init__(self):
            DynamicCore.__init__(self, [MathKw(), EchoKw()])
''').strip()

ROBOT_SRC = textwrap.dedent('''
    *** Settings ***
    Library    MiniLib

    *** Test Cases ***
    Add Works
        ${r}=    Add Numbers    2    3
        Should Be Equal As Integers    ${r}    5

    Echo Works
        ${r}=    Echo Text    hello
        Should Be Equal    ${r}    echo:hello

    Both In One Suite
        ${a}=    Add Numbers    10    20
        ${e}=    Echo Text    ${a}
        Should Be Equal    ${e}    echo:30
''').strip()


def main() -> int:
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d / "MiniLib.py").write_text(MINILIB_SRC)
        (d / "suite.robot").write_text(ROBOT_SRC)
        proc = subprocess.run(
            [sys.executable, "-m", "robot", "--outputdir", str(d), "suite.robot"],
            cwd=d, capture_output=True, text=True,
        )
        print("robot exit:", proc.returncode)
        print(proc.stdout[-1500:])
        if proc.returncode != 0:
            print(proc.stderr[-500:])
        # Parse output.xml for test counts
        out_xml = (d / "output.xml").read_text(errors="ignore")
        passes = out_xml.count('status="PASS"')
        fails = out_xml.count('status="FAIL"')
        print(f"output.xml: PASS markers={passes} FAIL markers={fails}")
    ok = (proc.returncode == 0) and (passes >= 3)
    print("PASS" if ok else "FAIL", "exp_05_robot_pythonlibcore")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
