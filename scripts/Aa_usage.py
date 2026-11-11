#!/usr/bin/env python3
"""Untitled usage/cost report: read a Hermes state.db and print token/cost totals.

Usage:
  Aa_usage.py                          # auto-find state.db (HERMES_HOME or ~/.hermes)
  Aa_usage.py --db PATH                # explicit state.db
  Aa_usage.py -n 10                    # last 10 sessions instead of 25
  Aa_usage.py --csv                    # machine-readable CSV

M4 hardening: Untitled must always be able to answer "what did I spend?" without
leaving the terminal. Data comes from the sessions table that upstream
hermes_state_usage keeps updated; nothing here writes to the database
(it is opened read-only/immutable, safe while the agent is running).
"""
import argparse
import ast
import csv
import os
import sqlite3
import sys
import time
from pathlib import Path

TOKEN_COLS = ("input_tokens", "output_tokens",
              "cache_read_tokens", "cache_write_tokens", "reasoning_tokens")

REPO = Path(__file__).resolve().parent.parent


def candidate_tool_names(repo_dir: Path) -> dict[str, str]:
    """Code paths the repo registers as tools: name -> defining module file.

    Static ast scan of tools/*.py for registry.register(name="x", ...) calls —
    importing the registry would drag the whole agent stack into what must
    stay a read-only report. Skips __init__/registry modules themselves.
    """
    out: dict[str, str] = {}
    tools_dir = repo_dir / "tools"
    if not tools_dir.is_dir():
        return out
    for f in sorted(tools_dir.glob("*.py")):
        if f.name in ("__init__.py", "registry.py"):
            continue
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"), filename=str(f.name))
        except (SyntaxError, OSError, UnicodeDecodeError):
            continue
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "register"):
                continue
            for kw in node.keywords:
                if kw.arg == "name" and isinstance(kw.value, ast.Constant) \
                        and isinstance(kw.value.value, str):
                    out.setdefault(kw.value.value, f.name)
                    break
    return out


def used_tool_names(db: sqlite3.Connection) -> set[str]:
    """Tool names with at least one recorded call (messages.tool_name)."""
    row = db.execute("SELECT count(*) FROM sqlite_master"
                     " WHERE type='table' AND name='messages'").fetchone()
    if not row or not row[0]:
        return set()
    used: set[str] = set()
    for r in db.execute("SELECT DISTINCT tool_name FROM messages"
                        " WHERE tool_name IS NOT NULL AND tool_name != ''"):
        used.add(str(r[0]))
    return used


def unused_code_paths(db: sqlite3.Connection, repo_dir: Path) -> list[tuple[str, str]]:
    """Registered tool code paths with zero recorded use — report-only.

    Candidates for an optional trim commit; never auto-removed. A name here
    may still be reachable through dynamic registration (browser_tool builds
    several names in a loop), so treat this as a hint list, not a verdict.
    """
    cands = candidate_tool_names(repo_dir)
    if not cands:
        return []
    used = used_tool_names(db)
    return [(n, f) for n, f in sorted(cands.items()) if n not in used]


def find_db() -> Path | None:
    for p in (
        os.environ.get("HERMES_STATE_DB"),
        os.path.join(os.environ.get("HERMES_HOME", ""), "state.db"),
        os.path.expanduser("~/.hermes/state.db"),
        os.path.expanduser("~/.hermes/profiles/untitled/state.db"),
    ):
        if p and Path(p).is_file():
            return Path(p)
    return None


def open_db(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(f"file:{path}?immutable=1", uri=True)
    db.row_factory = sqlite3.Row
    return db


def totals(db: sqlite3.Connection) -> dict:
    cols = ", ".join(f"COALESCE(SUM({c}), 0)" for c in TOKEN_COLS)
    row = db.execute(
        f"SELECT {cols}, COALESCE(SUM(estimated_cost_usd), 0),"
        f" COALESCE(SUM(actual_cost_usd), 0), COALESCE(SUM(api_call_count), 0),"
        f" count(*) FROM sessions"
    ).fetchone()
    keys = (*TOKEN_COLS, "estimated_cost_usd", "actual_cost_usd", "api_calls", "sessions")
    return dict(zip(keys, [float(v) for v in row]))


def per_model(db: sqlite3.Connection) -> list[dict]:
    cols = ", ".join(f"COALESCE(SUM({c}), 0)" for c in TOKEN_COLS)
    rows = db.execute(
        f"SELECT COALESCE(model, 'unknown') AS model, {cols},"
        f" COALESCE(SUM(estimated_cost_usd), 0), COALESCE(SUM(api_call_count), 0),"
        f" count(*) FROM sessions GROUP BY COALESCE(model, 'unknown') ORDER BY 2 DESC"
    ).fetchall()
    out = []
    for r in rows:
        d = dict(zip(("model", *TOKEN_COLS, "estimated_cost_usd", "api_calls", "sessions"),
                     [v if isinstance(v, str) else float(v) for v in r]))
        out.append(d)
    return out


def day(v: str) -> str:
    """started_at may be epoch seconds or an ISO string; show a plain date."""
    s = str(v or "").strip()
    try:
        return time.strftime("%Y-%m-%d", time.gmtime(float(s)))
    except ValueError:
        return s[:10]


def recent(db: sqlite3.Connection, n: int) -> list[dict]:
    cols = ", ".join(f"COALESCE({c}, 0)" for c in TOKEN_COLS)
    rows = db.execute(
        f"SELECT started_at, COALESCE(model, 'unknown'), {cols},"
        f" COALESCE(estimated_cost_usd, 0), COALESCE(api_call_count, 0)"
        f" FROM sessions ORDER BY started_at DESC LIMIT ?", (n,)).fetchall()
    out = []
    for r in rows:
        out.append(dict(zip(("started_at", "model", *TOKEN_COLS,
                             "estimated_cost_usd", "api_calls"), r)))
    return out


def fmt(v: float) -> str:
    return f"{v:,.0f}" if abs(v) >= 10 else f"{v:,.2f}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Untitled usage/cost report (read-only)")
    ap.add_argument("--db", type=Path, default=None, help="path to state.db")
    ap.add_argument("-n", type=int, default=25, help="recent sessions to list (default 25)")
    ap.add_argument("--csv", action="store_true", help="print CSV instead of text")
    ap.add_argument("--unused", action="store_true",
                    help="append the unused-code-paths report (report-only)")
    args = ap.parse_args()

    path = args.db or find_db()
    if not path:
        print("no state.db found; use --db PATH", file=sys.stderr)
        return 1
    try:
        db = open_db(path)
        t = totals(db)
        models = per_model(db)
        rec = recent(db, args.n)
    except sqlite3.Error as e:
        print(f"cannot read {path}: {e}", file=sys.stderr)
        return 1

    if args.csv:
        w = csv.writer(sys.stdout)
        w.writerow(["kind", *t.keys()])
        w.writerow(["total", *t.values()])
        for m in models:
            w.writerow(["model", *m.values()])
        for r in rec:
            w.writerow(["session", day(r["started_at"]), *list(r.values())[1:]])
        return 0

    print(f"db: {path}")
    print(f"sessions: {t['sessions']:.0f}   api calls: {t['api_calls']:.0f}")
    for c in TOKEN_COLS:
        print(f"  {c:20s} {fmt(t[c])}")
    print(f"  {'estimated cost usd':20s} ${t['estimated_cost_usd']:.4f}"
          f"   (actual ${t['actual_cost_usd']:.4f})")
    if models:
        print("by model:")
        for m in models:
            print(f"  {m['model'][:40]:40s} in {fmt(m['input_tokens']):>12}"
                  f"  out {fmt(m['output_tokens']):>10}"
                  f"  ${m['estimated_cost_usd']:.4f}  ({m['sessions']:.0f} sessions)")
    if rec:
        print(f"last {len(rec)} sessions:")
        for r in rec:
            print(f"  {day(r['started_at'])}  {r['model'][:28]:28s} in {fmt(r['input_tokens']):>10}"
                  f"  out {fmt(r['output_tokens']):>9}  ${r['estimated_cost_usd']:.4f}")
    if args.unused:
        try:
            un = unused_code_paths(db, REPO)
        except sqlite3.Error as e:
            print(f"\nunused code paths: cannot read ({e})")
            return 0
        if un:
            print(f"\nunused code paths ({len(un)}) — report-only candidates,"
                  " never auto-removed:")
            for n, f in un:
                print(f"  {n:30s} {f}")
        else:
            print("\nunused code paths: none found (all registered tools have"
                  " recorded use, or no candidate data)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
