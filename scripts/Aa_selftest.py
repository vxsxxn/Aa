#!/usr/bin/env python3
"""Aa self-test: what must pass before a source commit sticks.

Two layers:
  1. syntax smoke — every tracked .py file must compile;
  2. unit tests — python -m unittest discover in tests/Aa/.

Integration tests (spawning the real agent / writing to real profile state)
skip themselves when AA_GATE_RUNNING=1 — that is how self_edit.py's test gate
invokes this script to keep the gate fast and hermetic. Running this script
directly (no AA_GATE_RUNNING) runs the full suite including integration tests.
"""
import compileall
import os
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GATE = os.environ.get("AA_GATE_RUNNING") == "1"


def main() -> int:
    # 1. Syntax smoke: every tracked .py in the repo must compile.
    if not compileall.compile_dir(str(REPO), quiet=2, force=False):
        print("FAIL: python compile smoke (run with python3 -m compileall to see errors)")
        return 1
    print("compile smoke: ok")

    # 1b. Repo map smoke: Aa_repo_map.py must be able to map this repo's own
    #     source — the gate depends on it for symbol-aimed edits.
    import subprocess
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "Aa_repo_map.py"),
                        "--summary", str(REPO / "scripts")],
                       capture_output=True, text=True, timeout=120)
    if r.returncode != 0 or not r.stdout.strip():
        print(f"FAIL: repo map smoke ({r.stderr.strip() or 'empty output'})")
        return 1
    print(f"repo map: ok ({r.stdout.strip().splitlines()[-1]})")

    # 2. Unit tests. Discover with the repo root importable (tests/Aa imports
    #    tools.* and scripts.* directly). AA_SELFTEST_RUNNING lets
    #    test_Aa_selftest_direct skip — running Aa_selftest inside itself
    #    would recurse forever.
    sys.path.insert(0, str(REPO))
    os.environ["AA_SELFTEST_RUNNING"] = "1"
    if not (REPO / "tests" / "Aa").is_dir():
        print("unit tests: ok (0 tests — no tests/Aa directory)")
        return 0
    suite = unittest.defaultTestLoader.discover(
        start_dir=str(REPO / "tests" / "Aa"), top_level_dir=str(REPO))
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    if not result.wasSuccessful():
        print(f"FAIL: {len(result.failures)} failure(s), "
              f"{len(result.errors)} error(s)")
        return 1
    n = result.testsRun
    print(f"unit tests: ok ({n} test{'s' if n != 1 else ''}, AA_GATE_RUNNING={GATE})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
