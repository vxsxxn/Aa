"""Task receipts: a 2-3 line record the agent writes when a task finishes.

Evidence for the curator — goal, approach, what worked — stored as JSONL keyed by
task, linked to any skills the task touched. Cheap (one append, one line), and it
gives promotion/decay decisions something real to look at instead of raw use-counts.

Storage: ``<HERMES_HOME>/tasks/receipts.jsonl`` (one JSON object per line).
"""

import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

_logger = __import__("logging").getLogger(__name__)

_lock = threading.Lock()
_append_lock = threading.Lock()


def _receipts_file() -> Path:
    root = Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes"))
    path = root / "tasks" / "receipts.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def record_receipt(
    task_id: str,
    goal: str,
    approach: str,
    outcome: str,
    skills: Optional[List[str]] = None,
    status: str = "done",
) -> Dict[str, Any]:
    """Append a receipt line. Returns the stored record."""
    skills = [str(s).strip() for s in (skills or []) if str(s).strip()]
    rec = {
        "task_id": task_id or "",
        "ts": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        "goal": goal.strip()[:400],
        "approach": approach.strip()[:600],
        "outcome": outcome.strip()[:600],
        "skills": skills[:10],
        "status": status if status in ("done", "partial", "blocked") else "done",
    }
    with _append_lock:
        with _receipts_file().open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def list_receipts(limit: int = 20, task_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Most recent receipts, newest first. Filter by task_id when given."""
    path = _receipts_file()
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        _logger.debug("read receipts failed: %s", e)
        return []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if task_id and rec.get("task_id") != task_id:
            continue
        out.append(rec)
        if len(out) >= limit:
            break
    return out


def receipts_for_skill(skill_name: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Receipts that touched a given skill — promotion/decay evidence."""
    path = _receipts_file()
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    for line in reversed(lines):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if skill_name in (rec.get("skills") or []):
            out.append(rec)
            if len(out) >= limit:
                break
    return out


# --- Registry ---
from tools.registry import registry, tool_error  # noqa: E402

RECEIPT_SCHEMA = {
    "name": "task_receipt",
    "description": (
        "Write or read a task receipt — a 2-3 line record of a completed job "
        "(goal, approach, what worked). Call this once when a task finishes; "
        "it is the evidence the curator uses for skill promotion/decay."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["record", "list", "for_skill"],
                "description": "record a new receipt, list recent ones, or list receipts touching a skill.",
            },
            "task_id": {"type": "string", "description": "ID of the task this receipt is for."},
            "goal": {"type": "string", "description": "What the task was for (1 line)."},
            "approach": {"type": "string", "description": "How it was done (1 line)."},
            "outcome": {"type": "string", "description": "What worked / what was learned (1 line)."},
            "skills": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Skill names this task used or created.",
            },
            "status": {"type": "string", "enum": ["done", "partial", "blocked"]},
            "skill": {"type": "string", "description": "Skill name — for action=for_skill."},
            "limit": {"type": "integer", "minimum": 1, "maximum": 50},
        },
        "required": ["action"],
    },
}


def _handle(args: Dict[str, Any], **kw) -> str:
    action = args.get("action")
    if action == "record":
        rec = record_receipt(
            task_id=str(args.get("task_id") or kw.get("task_id") or ""),
            goal=str(args.get("goal") or ""),
            approach=str(args.get("approach") or ""),
            outcome=str(args.get("outcome") or ""),
            skills=args.get("skills") or [],
            status=str(args.get("status") or "done"),
        )
        return json.dumps({"ok": True, "receipt": rec}, ensure_ascii=False)
    if action == "list":
        return json.dumps(
            {"receipts": list_receipts(limit=int(args.get("limit") or 20), task_id=args.get("task_id"))},
            ensure_ascii=False,
        )
    if action == "for_skill":
        name = str(args.get("skill") or "").strip()
        if not name:
            return tool_error("action=for_skill requires `skill` (the skill name to look up).")
        return json.dumps({"receipts": receipts_for_skill(name, limit=int(args.get("limit") or 5))}, ensure_ascii=False)
    return tool_error(f"unknown action: {action}")


registry.register(
    name="task_receipt", toolset="skills", schema=RECEIPT_SCHEMA, emoji="🧾",
    handler=lambda args, **kw: _handle(args, **kw))
