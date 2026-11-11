"""First-run naming: the agent answers to whatever the user calls it.

On a blank install the first launch asks "What do you want to call me?" and
stamps the answer into the profile's SOUL.md identity line (HERMES_HOME's,
never a repo file — repo code stays generic per PLAN.md). The question fires
at most once per profile: only a SOUL.md that still holds the auto-seeded
default identity is personalized, and a file the user has already written is
never touched. Pressing Enter keeps the shipped default (untitled).
"""

from __future__ import annotations

import sys
from pathlib import Path

from hermes_cli.default_soul import DEFAULT_AGENT_NAME

NAMING_QUESTION = "What do you want to call me?"
MAX_NAME_LEN = 40


def _clean_name(raw: str) -> str:
    """Trim whitespace and wrapping quotes, cap the length. Empty -> ''."""
    name = raw.strip().strip("\"'`").strip()
    return name[:MAX_NAME_LEN].strip()


def identity_seeds() -> tuple[str, str]:
    """The full seeded identity paragraphs a naming stamp may rewrite.

    First the shipped default, then the pre-rebrand seed still present on
    installs that seeded SOUL.md before the name became configurable, then the
    "Untitled"-named seed from installs before the default became "untitled". A
    normalized SOUL.md must equal one of these exactly to be personalized —
    anything else is user intent and is never overwritten.
    """
    from hermes_cli.default_soul import (
        DEFAULT_SOUL_MD, IDENTITY_HEAD, LEGACY_IDENTITY_HEAD, LEGACY_AA_IDENTITY_HEAD,
    )

    behavior = DEFAULT_SOUL_MD[len(IDENTITY_HEAD):]  # " Be direct: ..."
    return (DEFAULT_SOUL_MD, LEGACY_IDENTITY_HEAD + behavior, LEGACY_AA_IDENTITY_HEAD + behavior)


def identity_is_seeded(soul_path: Path) -> bool:
    """True when *soul_path* still holds an auto-seeded (default) identity."""
    from hermes_cli.default_soul import _normalize_soul

    if not soul_path.is_file():
        return False
    norm = _normalize_soul(soul_path.read_text(encoding="utf-8"))
    return norm in (_normalize_soul(seed) for seed in identity_seeds())


def personalize(soul_path: Path, name: str) -> str | None:
    """Rewrite the seeded identity line's name in *soul_path*.

    Returns the new identity head, or None when the file does not hold a
    seeded default identity (missing, user-written, or already renamed) — in
    that case the file is never written.
    """
    from hermes_cli.default_soul import (
        DEFAULT_SOUL_MD, IDENTITY_HEAD, IDENTITY_TAIL, _normalize_soul,
    )

    if not name or not name.strip():
        return None
    if not soul_path.is_file():
        return None
    norm = _normalize_soul(soul_path.read_text(encoding="utf-8"))
    matched = next((seed for seed in identity_seeds() if norm == _normalize_soul(seed)), None)
    if matched is None:
        return None
    # " Be direct: ..." — the behavior spec every seeded identity shares; the stamp only swaps
    # the name slot, so a blank press stays byte-identical to the shipped default.
    behavior = DEFAULT_SOUL_MD[len(IDENTITY_HEAD):]
    new_head = f"You are {name}, {IDENTITY_TAIL}"
    tmp = soul_path.with_name(soul_path.name + ".naming.tmp")
    tmp.write_text(new_head + behavior + "\n", encoding="utf-8")
    tmp.replace(soul_path)
    return new_head


def offer_naming(*, input_fn=input, is_tty=None) -> str | None:
    """Interactive first-run naming.

    Asks NAMING_QUESTION once, on a blank install, and stamps the answer into
    the profile's SOUL.md. Returns the stamped name, or None when the question
    was not offered (no TTY, nothing to personalize) or was interrupted — an
    interrupted profile simply gets asked again next launch.
    """
    from hermes_constants import get_hermes_home

    tty = sys.stdin.isatty if is_tty is None else is_tty
    if not tty():
        return None
    soul = Path(get_hermes_home()) / "SOUL.md"
    if not identity_is_seeded(soul):
        return None  # the user's own SOUL.md or nothing seeded — never ask
    try:
        raw = input_fn(f"  {NAMING_QUESTION} (Enter = {DEFAULT_AGENT_NAME}) ")
    except (KeyboardInterrupt, EOFError):
        print()
        return None
    name = _clean_name(raw) or DEFAULT_AGENT_NAME
    personalize(soul, name)
    print(f"  Okay — {name} it is. Rename any time by editing SOUL.md.")
    return name
