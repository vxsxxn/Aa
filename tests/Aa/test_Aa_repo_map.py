"""Aa repo map: symbol-aimed edits (scripts/Aa_repo_map.py).

Line spans are the point — a patch must be able to name file + symbol +
line range instead of guessing at fuzzy text. These tests pin the spans,
the directory walk, and the CLI contract the self-test gate relies on.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.Aa_repo_map import collect_files, map_file, summarize

REPO = Path(__file__).resolve().parent.parent.parent
SAMPLE = '''\
import ast

class Greeter:
    def hello(self):
        return 1

    async def aloha(self):
        return 2

def top_level():
    return 3

def nested_outer():
    def nested_inner():
        return 4
    return nested_inner()
'''


class RepoMapTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.sample = self.dir / "sample.py"
        self.sample.write_text(SAMPLE, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_class_method_and_function_spans(self):
        syms = {s["name"]: s for s in map_file(self.sample)}
        self.assertEqual(syms["Greeter"]["kind"], "class")
        self.assertEqual(syms["Greeter"]["line"], 3)
        self.assertEqual(syms["Greeter"]["end_line"], 8)  # spans both methods
        self.assertEqual(syms["Greeter.hello"]["line"], 4)
        self.assertEqual(syms["Greeter.hello"]["end_line"], 5)
        self.assertEqual(syms["Greeter.aloha"]["kind"], "method")
        self.assertEqual(syms["top_level"]["kind"], "function")
        self.assertEqual(syms["top_level"]["line"], 10)

    def test_nested_functions_stay_out(self):
        names = {s["name"] for s in map_file(self.sample)}
        self.assertIn("nested_outer", names)
        self.assertNotIn("nested_inner", names)

    def test_unparsable_file_maps_empty(self):
        bad = self.dir / "bad.py"
        bad.write_text("def broken(:\n", encoding="utf-8")
        self.assertEqual(map_file(bad), [])

    def test_collect_walks_dirs_and_skips_noise(self):
        pycache = self.dir / "__pycache__"
        pycache.mkdir()
        (pycache / "junk.py").write_text("x = 1\n", encoding="utf-8")
        (self.dir / "real.py").write_text("x = 1\n", encoding="utf-8")
        (self.dir / "notes.txt").write_text("not python\n", encoding="utf-8")
        found = collect_files([str(self.dir)])
        self.assertEqual([f.name for f in found], ["real.py", "sample.py"])
        # missing path is simply absent from the walk (CLI reports it separately)
        self.assertEqual(collect_files([str(self.dir / "nope")]), [])

    def test_summary_counts(self):
        rows = summarize(collect_files([str(self.sample)]))
        self.assertEqual(rows, [{"path": str(self.sample), "symbols": 5}])

    def test_cli_json_and_missing_path_exit(self):
        r = subprocess.run([sys.executable, str(REPO / "scripts" / "Aa_repo_map.py"),
                            "--json", str(self.sample)], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        data = json.loads(r.stdout)
        self.assertIn("Greeter", [s["name"] for s in data[str(self.sample)]])
        r = subprocess.run([sys.executable, str(REPO / "scripts" / "Aa_repo_map.py"),
                            str(self.dir / "nope")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)

    def test_gate_smoke_maps_own_source(self):
        """The self-test gate runs the map on scripts/ — it must be non-empty."""
        r = subprocess.run([sys.executable, str(REPO / "scripts" / "Aa_repo_map.py"),
                            "--summary", str(REPO / "scripts")],
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        total = [ln for ln in r.stdout.splitlines() if ln.startswith("total:")]
        self.assertTrue(total and not total[0].endswith("0 symbols"))


if __name__ == "__main__":
    unittest.main()
