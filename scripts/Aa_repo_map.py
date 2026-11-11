#!/usr/bin/env python3
"""Untitled repo map: aim edits at real symbols instead of fuzzy text.

Stdlib-only ast extraction of classes and functions with line spans, so a
patch can name the symbol it targets (file + line range) instead of guessing
at text. Works on files or directories:

  Aa_repo_map.py agent/prompt_builder.py          # one file
  Aa_repo_map.py scripts tools                    # recurse both dirs
  Aa_repo_map.py scripts --summary                # per-file counts only
  Aa_repo_map.py scripts --json                   # machine-readable

Top-level defs and class methods only — nested closures stay out of the map
on purpose: they are not stable edit targets. Directories skip __pycache__,
.git, virtualenvs and similar noise. Exit 0 with a map, 2 on bad paths.
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

SKIP_DIRS = {"__pycache__", ".git", ".venv", "venv", "node_modules", ".tox", ".mypy_cache"}


def collect_files(paths: list[str]) -> list[Path]:
    """Expand file/dir arguments into a sorted list of .py files."""
    files: set[Path] = set()
    for raw in paths:
        p = Path(raw)
        if p.is_file() and p.suffix == ".py":
            files.add(p)
        elif p.is_dir():
            for f in p.rglob("*.py"):
                if not SKIP_DIRS.intersection(f.parts):
                    files.add(f)
    return sorted(files)


def map_file(path: Path) -> list[dict]:
    """Symbols of one file: {kind, name, line, end_line}. Unparsable -> [].

    A file that no longer parses is a finding in itself (broken working
    tree); the compile smoke in Aa_selftest.py is the authority for that, so
    this stays quiet instead of failing the whole map.
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (SyntaxError, OSError, UnicodeDecodeError):
        return []
    out: list[dict] = []
    for node in tree.body:  # top-level classes and functions
        kind = "class" if isinstance(node, ast.ClassDef) else "function"
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            out.append({"kind": kind, "name": node.name,
                        "line": node.lineno, "end_line": node.end_lineno or node.lineno})
            if isinstance(node, ast.ClassDef):
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        out.append({"kind": "method", "name": f"{node.name}.{sub.name}",
                                    "line": sub.lineno,
                                    "end_line": sub.end_lineno or sub.lineno})
    return out


def summarize(files: list[Path]) -> list[dict]:
    """Per-file symbol counts (directory summary mode)."""
    return [{"path": str(f), "symbols": len(map_file(f))} for f in files]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Untitled repo map: classes/functions with line spans")
    ap.add_argument("paths", nargs="+", help="file(s) or directory to map")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--summary", action="store_true", help="per-file counts only")
    args = ap.parse_args(argv)

    files = collect_files(args.paths)
    missing = [p for p in args.paths if not Path(p).exists()]
    if missing:
        print(f"Aa_repo_map: no such path(s): {', '.join(missing)}", file=sys.stderr)
        return 2
    if args.summary:
        rows = summarize(files)
        if args.json:
            print(json.dumps(rows, indent=2))
        else:
            total = sum(r["symbols"] for r in rows)
            for r in rows:
                print(f"{r['path']}: {r['symbols']} symbols")
            print(f"total: {len(rows)} file(s), {total} symbols")
        return 0

    result = {str(f): map_file(f) for f in files}
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for f in files:
            print(f)
            for s in map_file(f):
                print(f"  {s['kind']:8} {s['name']:40} L{s['line']}-{s['end_line']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
