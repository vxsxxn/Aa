#!/usr/bin/env python3
"""Aa's self-edit helper: commit changes to this repo, safely.

Usage:
  self_edit.py commit -m "message" PATH [PATH...]   scan + stage + test + commit
  self_edit.py revert                                revert the last commit
  self_edit.py log [-n N] [--all]                    recent self-edit commits
  self_edit.py status                                git status --short
  self_edit.py soul -m "text"                        dated changelog entry in
                                                     SOUL.md, committed via gate

Rules enforced here:
  - Only files inside this repo may be committed.
  - Every staged file is scanned for prompt-injection payloads
    (tools/threat_patterns.py): injection/exfiltration/invisible-unicode
    findings BLOCK the commit; soft C2-vocabulary hits only warn.
  - Python files must compile; JSON must parse; YAML must parse.
  - Commits touching source code (agent/, tools/, hermes_cli/, scripts/,
    tests/ — *.py/*.sh) must pass the Aa self-test first
    (scripts/Aa_selftest.py); a failing test blocks the commit.
  - Commit messages get an "Aa:self-edit:" prefix automatically (unless present).
  - `revert` undoes the last commit in one step (git revert, no editor)
    and refuses on a dirty tree.
"""
import argparse
import json
import os
import py_compile
import subprocess
import sys
import time
from pathlib import Path

try:
    import yaml
except ImportError:  # yaml optional; skip yaml checks if missing
    yaml = None

# Allow running from anywhere: make tools/ importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.threat_patterns import first_threat_message, scan_for_threats  # noqa: E402

PREFIX = "Aa:self-edit:"
REPO = Path(__file__).resolve().parent.parent
SELFTEST = REPO / "scripts" / "Aa_selftest.py"
SOUL = REPO / "SOUL.md"
SOUL_HEADING = "## Changelog"

# Source paths that must pass the test gate before a commit sticks.
CODE_DIRS = ("agent", "tools", "hermes_cli", "scripts", "tests")
SOURCE_SUFFIXES = (".py", ".sh")


def git(*args, **kw):
    return subprocess.run(["git", "-C", str(REPO), *args],
                          capture_output=True, text=True, **kw)


def is_source_path(p: Path) -> bool:
    rel = p.relative_to(REPO)
    return (rel.suffix.lower() in SOURCE_SUFFIXES
            and (len(rel.parts) == 1 or rel.parts[0] in CODE_DIRS))


def check_file(path: Path) -> str | None:
    """Return an error string if the file fails its syntax check, else None."""
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as e:
        return f"unreadable: {e}"
    suffix = path.suffix.lower()
    if suffix == ".py":
        try:
            compile(text, str(path), "exec")
        except SyntaxError as e:
            return f"python syntax error: {e}"
    elif suffix == ".json":
        try:
            json.loads(text)
        except json.JSONDecodeError as e:
            return f"json error: {e}"
    elif suffix in (".yaml", ".yml") and yaml is not None:
        try:
            yaml.safe_load(text)
        except Exception as e:
            return f"yaml error: {e}"
    return None


def added_lines_text(path: Path) -> str | None:
    """The text this commit would introduce, from the working-tree diff.

    The gate judges what a commit ADDS, not upstream text the file already
    carries — pre-existing matches would otherwise block every future edit of
    the file forever. New files have no pre-existing text, so their whole
    content counts as added (None signals that whole-file scan).
    """
    r = git("diff", "HEAD", "-U0", "--", str(path))
    if r.returncode:
        return None  # diff failed — fall back to whole-file scan
    if not r.stdout.strip():
        # No diff: an untracked file (whole content is the addition) or an
        # unchanged tracked file (nothing new to scan).
        return None if git("ls-files", "--error-unmatch", "--", str(path)).returncode else ""
    added = [line[1:] for line in r.stdout.splitlines()
             if line.startswith("+") and not line.startswith("+++") ]
    return "\n".join(added)


def scan_file(path: Path) -> tuple[list[str], list[str], str]:
    """Injection scan of a staged file — only the lines the commit adds.

    Returns (blocks, warns, first): block-level findings (hard injection/exfil/
    persistence/secrets/invisible-unicode) and warn-level findings (soft
    C2 vocabulary with known false positives). Only readable text is scanned.
    """
    try:
        whole = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return [], []  # binary or unreadable; syntax check handles unreadable
    added = added_lines_text(path)
    text = whole if added is None else added
    blocks = sorted(set(scan_for_threats(text, scope="all"))
                    | set(scan_for_threats(text, scope="strict")))
    warns = sorted(set(scan_for_threats(text, scope="context"))
                   - set(scan_for_threats(text, scope="strict"))
                   - set(blocks))
    first = first_threat_message(text, scope="strict") or ""
    return blocks, warns, first


def run_selftest() -> tuple[bool, str]:
    """Run scripts/Aa_selftest.py; return (ok, output)."""
    env = dict(os.environ, AA_GATE_RUNNING="1")
    r = subprocess.run([sys.executable, str(SELFTEST)], capture_output=True,
                       text=True, cwd=str(REPO), env=env, timeout=300)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


# Large diffs may aim the gate at the tests that cover the changed files
# instead of the whole suite. Thresholds are generous: the full suite is the
# default until it actually outgrows a few seconds.
LARGE_DIFF_FILES = 4
LARGE_DIFF_LINES = 200


def _added_line_count(p: Path) -> int:
    r = git("diff", "HEAD", "-U0", "--", str(p))
    return sum(1 for ln in r.stdout.splitlines()
               if ln.startswith("+") and not ln.startswith("+++"))


def is_large_diff(paths: list[Path]) -> bool:
    src = [p for p in paths if is_source_path(p) and p.suffix == ".py"]
    if len(src) >= LARGE_DIFF_FILES:
        return True
    return sum(_added_line_count(p) for p in src) >= LARGE_DIFF_LINES


def map_tests(paths: list[Path]) -> list[str]:
    """tests/Aa modules whose text mentions a changed source file's stem.

    Stem mention is the deliberate heuristic: every tests/Aa file names the
    module it covers (its own name or in its docstring/imports), so a text
    hit means coverage; no hit means no known coverage.
    """
    stems = [p.stem for p in paths]
    picked = []
    for t in sorted((REPO / "tests" / "Aa").glob("test_*.py")):
        if any(s in t.read_text(encoding="utf-8", errors="ignore") for s in stems):
            picked.append(f"tests.Aa.{t.stem}")
    return picked


def run_selected_tests(modules: list[str]) -> tuple[bool, str]:
    """Run only the given unittest modules (AA_GATE_RUNNING still set)."""
    env = dict(os.environ, AA_GATE_RUNNING="1")
    r = subprocess.run([sys.executable, "-m", "unittest", *modules],
                       capture_output=True, text=True, cwd=str(REPO),
                       env=env, timeout=300)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def compile_paths(paths: list[Path]) -> tuple[bool, str]:
    """Byte-compile the changed .py files; the minimum smoke for any diff."""
    import py_compile
    errs = []
    for p in paths:
        if p.suffix != ".py":
            continue
        try:
            py_compile.compile(str(p), doraise=True)
        except py_compile.PyCompileError as e:
            errs.append(str(e))
    return not errs, "\n".join(errs)


def cmd_commit(args):
    paths = [Path(p).resolve() for p in args.paths]
    for p in paths:
        if not p.exists():
            return fail(f"not found: {p}")
        if REPO not in p.parents and p != REPO:
            return fail(f"outside this repo, refusing: {p}")
        err = check_file(p)
        if err:
            return fail(f"{p.name}: {err}")
        blocks, warns, first = scan_file(p)
        if blocks:
            detail = ", ".join(blocks)
            return fail(f"{p.name}: injection scan blocked ({detail})\n{first}")
        for w in warns:
            print(f"warning: {p.name}: soft injection-scan hit: {w}",
                  file=sys.stderr)

    # Test gate: source-code changes must pass the self-test first.
    if any(is_source_path(p) for p in paths):
        if is_large_diff(paths):
            modules = map_tests(paths)
            print(f"self-test: large diff — targeted run: "
                  f"{', '.join(modules) or 'compile smoke only'}", file=sys.stderr)
            ok, out = compile_paths(paths)
            if ok and modules:
                ok, out = run_selected_tests(modules)
            label = f"targeted tests ({', '.join(modules) or 'compile smoke'})"
        else:
            print("self-test: running scripts/Aa_selftest.py ...", file=sys.stderr)
            ok, out = run_selftest()
            label = "scripts/Aa_selftest.py"
        if not ok:
            return fail("test gate failed — commit refused:\n" + out)
        print(f"self-test: passed ({label})", file=sys.stderr)

    r = git("add", "--", *[str(p) for p in paths])
    if r.returncode:
        return fail(r.stderr)
    msg = args.message if args.message.startswith(PREFIX) else f"{PREFIX} {args.message}"
    r = git("commit", "-m", msg)
    if r.returncode:
        # Nothing staged or commit failed — make sure we don't leave junk staged.
        git("reset", "--", *[str(p) for p in paths])
        return fail(r.stdout + r.stderr)
    print(msg)
    return 0


def cmd_revert(_args):
    r = git("status", "--porcelain")
    if r.returncode:
        return fail(r.stderr)
    if r.stdout.strip():
        # A revert into a dirty tree can mix unrelated edits into the revert commit
        # or fail confusingly halfway; the tree must be clean first.
        return fail("working tree is dirty; commit or stash before reverting:\n" + r.stdout)
    r = git("revert", "--no-edit", "HEAD")
    print(r.stdout + r.stderr)
    return r.returncode


def cmd_log(args):
    r = git("log", f"-n{args.n}", "--oneline", "--", ".")
    if r.returncode:
        return fail(r.stderr)
    for line in r.stdout.splitlines():
        if line.startswith(PREFIX[:14]) or PREFIX in line or args.all:
            print(line)
    return 0


def cmd_status(_args):
    r = git("status", "--short")
    print(r.stdout or "(clean)")
    return r.returncode


def cmd_soul(args):
    """Append a dated entry to SOUL.md's changelog, then commit it via the gate."""
    if not SOUL.is_file():
        return fail(f"not found: {SOUL}")
    text = SOUL.read_text(encoding="utf-8")
    entry = f"- {time.strftime('%Y-%m-%d')} {args.message.strip()}"
    if SOUL_HEADING in text:
        text = text.replace(SOUL_HEADING, f"{SOUL_HEADING}\n{entry}", 1)
    else:
        if text and not text.endswith("\n"):
            text += "\n"
        text += f"\n{SOUL_HEADING}\n\n{entry}\n"
    tmp = SOUL.with_suffix(".md.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(SOUL)
    return cmd_commit(argparse.Namespace(
        message=f"soul: {args.message.strip()}", paths=[str(SOUL)]))


def fail(msg):
    print(msg, file=sys.stderr)
    return 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("commit", help="scan, check, stage, test and commit files")
    c.add_argument("-m", "--message", required=True)
    c.add_argument("paths", nargs="+")
    sub.add_parser("revert", help="revert last commit")
    lg = sub.add_parser("log", help="recent self-edit commits")
    lg.add_argument("-n", type=int, default=10)
    lg.add_argument("--all", action="store_true")
    sub.add_parser("status")
    so = sub.add_parser(
        "soul", help="append a dated entry to SOUL.md's changelog and commit it")
    so.add_argument("-m", "--message", required=True)
    args = ap.parse_args()
    sys.exit({"commit": cmd_commit, "revert": cmd_revert,
              "log": cmd_log, "status": cmd_status,
              "soul": cmd_soul}[args.cmd](args))


if __name__ == "__main__":
    main()
