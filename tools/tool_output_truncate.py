"""Head/tail truncation for oversized tool output (terminal, execute_code, MCP results).

One algorithm and one notice wording: 40% head (errors surface early) / 60% tail (the most
recent lines matter most) around a single ``... [<LABEL> TRUNCATED - N <unit> omitted out of
T total] ...`` marker, so downstream code that recognises the marker sees one shape. Limits
live in ``tools/tool_output_limits.py``; line-snapped, path-bearing footers (web/browser,
read_file pagination) are different products and stay separate.
"""

from __future__ import annotations

HEAD_RATIO = 0.4


def truncation_notice(omitted: int, total: int, *, label: str = "OUTPUT", unit: str = "chars") -> str:
    return f"\n\n... [{label} TRUNCATED - {omitted:,} {unit} omitted out of {total:,} total] ...\n\n"


def head_tail_split(budget: int) -> tuple[int, int]:
    """``(head, tail)`` character budgets for ``budget`` total."""
    head = int(budget * HEAD_RATIO)
    return head, budget - head


def compress_repeated_lines(text: str, min_run: int = 3) -> str:
    """Collapse runs of identical lines into one line plus a repetition note.

    Log-style tool output (builds, test runs, progress spinners) often spends most
    of its budget repeating the same line hundreds of times. Runs of ``min_run`` or
    more identical consecutive non-empty lines are replaced by the first line and a
    compact ``[repeated N×]`` marker, preserving head/tail structure and line order.
    """
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        j = i + 1
        if lines[i].strip():
            while j < n and lines[j] == lines[i]:
                j += 1
        if j - i >= min_run:
            out.append(lines[i])
            out.append(f"[repeated {j - i}× identical lines omitted]")
            i = j
        else:
            out.append(lines[i])
            i += 1
    return "\n".join(out)


def truncate_head_tail(text: str, max_chars: int, *, label: str = "OUTPUT") -> str:
    """``text`` unchanged when it fits ``max_chars``; otherwise repeated-line compression
    first, then head + notice + tail (the kept text is exactly ``max_chars`` long)."""
    if len(text) <= max_chars:
        return text
    compressed = compress_repeated_lines(text)
    if len(compressed) <= max_chars:
        return compressed
    text = compressed
    head, tail = head_tail_split(max_chars)
    omitted = len(text) - head - tail
    return text[:head] + truncation_notice(omitted, len(text), label=label) + text[-tail:]
