#!/usr/bin/env python3
"""Untitled memory consolidation: inspect and prune a profile MEMORY.md to a budget.

Memory files hold entries separated by lines that are exactly "§". Entries
are appended over time, so the top of the file holds the oldest material.

Usage:
  Aa_memory.py [--memory PATH] [--budget N]      report budget usage (dry run)
  Aa_memory.py --apply [--memory PATH] [--budget N]
                                                 archive overflow to
                                                 MEMORY-archive.md

Overflow handling: oldest entries (top of file) move to MEMORY-archive.md in
the same directory, "§" separators preserved, until the kept file fits the
budget. Nothing is written without --apply.
"""
import argparse
import os
import re
import sys
from pathlib import Path

SEP_RE = re.compile(r"(?m)^[ \t]*§[ \t]*$\n?")
JOINER = "§\n"
DEFAULT_BUDGET = 2200


def find_memory() -> Path | None:
    for cand in (
        os.environ.get("HERMES_HOME", "") and Path(os.environ["HERMES_HOME"]) / "MEMORY.md",
        Path.home() / ".hermes" / "MEMORY.md",
        Path.home() / ".hermes" / "profiles" / "untitled" / "MEMORY.md",
    ):
        if cand and cand.is_file():
            return cand
    return None


def split_entries(text: str) -> list[str]:
    """Split on "§" separator lines; rejoining with JOINER round-trips."""
    return SEP_RE.split(text)


def entry_label(entry: str) -> str:
    line = next((ln for ln in entry.splitlines() if ln.strip()), "")
    return line.strip()[:60]


def plan_archive(text: str, budget: int) -> tuple[list[str], list[str]]:
    """(entries to move, entries to keep) so the kept file fits the budget."""
    parts = [p for p in split_entries(text) if p.strip()]
    total = sum(len(p) for p in parts)
    moved: list[str] = []
    while total > budget and len(parts) > 1:
        moved.append(parts.pop(0))
        total = sum(len(p) for p in parts)
    return moved, parts


def cmd_report(mem: Path, budget: int) -> int:
    text = mem.read_text(encoding="utf-8")
    parts = [p for p in split_entries(text) if p.strip()]
    print(f"memory: {mem}")
    print(f"size: {len(text)} chars   entries: {len(parts)}   budget: {budget}")
    over = len(text) > budget
    moved, _kept = plan_archive(text, budget)
    if over:
        print(f"over budget by {len(text) - budget} chars; "
              f"oldest {len(moved)} entr{'y' if len(moved) == 1 else 'ies'} "
              f"would move to MEMORY-archive.md (--apply to write):")
        for e in moved:
            print(f"  - ({len(e)} chars) {entry_label(e)}")
    else:
        print("within budget; nothing to archive")
    return 0


def cmd_apply(mem: Path, budget: int) -> int:
    text = mem.read_text(encoding="utf-8")
    moved, kept = plan_archive(text, budget)
    if not moved:
        if len(text) <= budget:
            print(f"memory: {mem} within budget "
                  f"({len(text)} chars <= {budget}); nothing to do")
        else:
            print(f"memory: {mem} over budget ({len(text)} chars > {budget}) "
                  f"but a single oversized entry cannot be split; nothing to do")
        return 0
    kept_text = JOINER.join(kept)
    if not kept_text.endswith("\n"):
        kept_text += "\n"

    arch = mem.with_name("MEMORY-archive.md")
    old = arch.read_text(encoding="utf-8") if arch.is_file() else ""
    if old and not old.endswith("\n"):
        old += "\n"
    arch_text = old + JOINER + JOINER.join(moved)

    mem.write_text(kept_text, encoding="utf-8")
    arch.write_text(arch_text, encoding="utf-8")
    print(f"archived {len(moved)} entries ({sum(len(e) for e in moved)} chars) "
          f"from {mem.name} to {arch.name}")
    print(f"kept file: {len(kept_text)} chars (budget {budget})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=(__doc__ or "Untitled memory consolidation").splitlines()[0])
    ap.add_argument("--memory", type=Path, help="path to MEMORY.md (default: auto-detect)")
    ap.add_argument("--budget", type=int, default=DEFAULT_BUDGET,
                    help=f"character budget (default {DEFAULT_BUDGET})")
    ap.add_argument("--apply", action="store_true", help="write the archive (default: report only)")
    args = ap.parse_args()

    mem = args.memory
    if mem is None:
        mem = find_memory()
    if mem is None:
        print("no MEMORY.md found; use --memory PATH", file=sys.stderr)
        return 1
    if not mem.is_file():
        print(f"not found: {mem}", file=sys.stderr)
        return 1
    try:
        mem.read_text(encoding="utf-8")
    except OSError as e:
        print(f"cannot read {mem}: {e}", file=sys.stderr)
        return 1
    return cmd_apply(mem, args.budget) if args.apply else cmd_report(mem, args.budget)


if __name__ == "__main__":
    sys.exit(main())
