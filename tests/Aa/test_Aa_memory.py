"""Unit tests for scripts/Aa_memory.py — memory consolidation.

Run directly:  python3 -m unittest tests.Untitled.test_Aa_memory -v
(or via scripts/Aa_selftest.py).
"""
import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def _find_repo() -> Path:
    here = Path(__file__).resolve().parent          # tests/Untitled
    candidates = [here.parent.parent, Path.cwd(), *Path.cwd().parents]
    for cand in candidates:
        if (cand / "scripts" / "Aa_memory.py").exists():
            return cand.resolve()
    raise RuntimeError("cannot locate Untitled repo root (scripts/Aa_memory.py)")


REPO = _find_repo()

AA_MEMORY = REPO / "scripts" / "Aa_memory.py"


def _load_Aa_memory():
    spec = importlib.util.spec_from_file_location("Aa_memory", AA_MEMORY)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # noqa: arg-less module import, no side effects
    return mod


Aa_memory = _load_Aa_memory()


def run(*args, **kw):
    kw.setdefault("timeout", 60)
    return subprocess.run([sys.executable, *args], capture_output=True,
                          text=True, **kw)


def make_memory(tmp: Path, sizes) -> Path:
    """Write a valid §-separated MEMORY.md with entries of the given sizes.

    Entries are joined with a newline + "§" line + newline so the separator
    is always alone on its line (what SEP_RE requires).
    """
    parts = [f"entry {i}\n" + "x" * n for i, n in enumerate(sizes)]
    p = tmp / "MEMORY.md"
    p.write_text("\n§\n".join(parts) + "\n", encoding="utf-8")
    return p


class AaMemoryUnit(unittest.TestCase):
    """Importable internals behave per the design notes."""

    def test_split_rejoin_roundtrip(self):
        text = "one\n\n§\n\ntwo\n\n§\n\nthree\n"
        parts = Aa_memory.split_entries(text)
        self.assertEqual([p.strip() for p in parts],
                         ["one", "two", "three"])
        self.assertEqual(Aa_memory.split_entries(Aa_memory.JOINER.join(parts)),
                         parts)
        self.assertEqual(Aa_memory.JOINER.join(parts), text)

    def test_plan_archive_moves_oldest_first(self):
        tmp = Path(tempfile.mkdtemp(prefix="mem_unit_"))
        try:
            p = make_memory(tmp, [20, 20, 20])
            moved, kept = Aa_memory.plan_archive(p.read_text(), 30)
            self.assertEqual([m.strip() for m in moved],
                             ["entry 0\n" + "x" * 20, "entry 1\n" + "x" * 20])
            self.assertEqual([k.strip() for k in kept], ["entry 2\n" + "x" * 20])
            self.assertLessEqual(sum(len(k) for k in kept), 30)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_plan_archive_never_moves_last_entry(self):
        tmp = Path(tempfile.mkdtemp(prefix="mem_unit_"))
        try:
            p = make_memory(tmp, [10])
            moved, kept = Aa_memory.plan_archive(p.read_text(), 5)
            self.assertEqual(moved, [])
            self.assertEqual(len(kept), 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class AaMemoryCli(unittest.TestCase):
    """CLI: dry-run by default; --apply archives overflow; no-op in budget."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="mem_cli_"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_report_is_dry_run(self):
        p = make_memory(self.tmp, [40, 40, 40])
        r = run(AA_MEMORY, "--memory", str(p), "--budget", "30")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("over budget", r.stdout)
        self.assertEqual(p.read_text().count("entry"), 3)   # untouched
        self.assertFalse((self.tmp / "MEMORY-archive.md").exists())

    def test_apply_moves_overflow_to_archive(self):
        p = make_memory(self.tmp, [40, 40, 40])
        r = run(AA_MEMORY, "--apply", "--memory", str(p), "--budget", "30")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("archived", r.stdout)
        kept = p.read_text(encoding="utf-8")
        arch = (self.tmp / "MEMORY-archive.md").read_text(encoding="utf-8")
        self.assertIn("entry 0", arch)
        self.assertIn("entry 1", arch)
        self.assertNotIn("entry 0", kept)
        self.assertNotIn("entry 1", kept)
        self.assertIn("entry 2", kept)
        # Re-run on the reduced state: last entry cannot move -> no-op, rc 0.
        r2 = run(AA_MEMORY, "--apply", "--memory", str(p), "--budget", "30")
        self.assertEqual(r2.returncode, 0, r2.stderr)
        self.assertIn("nothing to do", r2.stdout)

    def test_apply_within_budget_is_noop(self):
        p = make_memory(self.tmp, [10, 10])
        r = run(AA_MEMORY, "--apply", "--memory", str(p), "--budget", "100")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("within budget", r.stdout)
        self.assertFalse((self.tmp / "MEMORY-archive.md").exists())

    def test_missing_memory_refused(self):
        env = dict(os.environ)
        env.pop("HERMES_HOME", None)
        r = run(AA_MEMORY, "--memory", "/nonexistent/MEMORY.md", env=env)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("not found", r.stderr)


if __name__ == "__main__":
    unittest.main()
