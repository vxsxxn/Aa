"""Aa usage report: unused-code-paths section (scripts/Aa_usage.py --unused).

Report-only by contract: the report never removes anything, and a name it
flags may still be reachable through dynamic registration — so the tests pin
extraction fidelity and the zero-use logic, not a removal behavior.
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.Aa_usage import candidate_tool_names, unused_code_paths, used_tool_names


class UnusedCodePathsTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self._tmp.name)
        (self.repo / "tools").mkdir()
        (self.repo / "tools" / "sample_tool.py").write_text(
            'registry.register(\n    name="sample_tool", toolset="cli",\n'
            '    schema={"name": "sample_tool"})\n', encoding="utf-8")
        (self.repo / "tools" / "other_tool.py").write_text(
            'registry.register(name="other_tool", toolset="cli", schema={})\n',
            encoding="utf-8")
        (self.repo / "tools" / "registry.py").write_text(
            "def register(**kw):\n    pass\n", encoding="utf-8")
        (self.repo / "tools" / "__init__.py").write_text("", encoding="utf-8")
        self.db = sqlite3.connect(":memory:")

    def tearDown(self):
        self.db.close()
        self._tmp.cleanup()

    def _use(self, *names):
        self.db.execute("CREATE TABLE IF NOT EXISTS messages (tool_name TEXT)")
        for n in names:
            self.db.execute("INSERT INTO messages VALUES (?)", (n,))

    def test_static_extraction_finds_registered_names(self):
        names = candidate_tool_names(self.repo)
        self.assertEqual(names, {"sample_tool": "sample_tool.py",
                                 "other_tool": "other_tool.py"})

    def test_unparsable_tool_file_is_skipped(self):
        (self.repo / "tools" / "bad_tool.py").write_text("def broken(:\n",
                                                         encoding="utf-8")
        self.assertEqual(set(candidate_tool_names(self.repo)),
                         {"sample_tool", "other_tool"})

    def test_no_messages_table_means_no_use_recorded(self):
        self.assertEqual(used_tool_names(self.db), set())
        unused = unused_code_paths(self.db, self.repo)
        self.assertEqual([n for n, _ in unused], ["other_tool", "sample_tool"])

    def test_used_names_are_not_reported(self):
        self._use("sample_tool")
        unused = unused_code_paths(self.db, self.repo)
        self.assertEqual([n for n, _ in unused], ["other_tool"])

    def test_all_used_means_empty_report(self):
        self._use("sample_tool", "other_tool")
        self.assertEqual(unused_code_paths(self.db, self.repo), [])


if __name__ == "__main__":
    unittest.main()
