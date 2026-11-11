# Untitled — custom agent forked from Hermes

Fork of Hermes Agent v0.22.5 (bf0203a794), branch `untitled`.

## What Untitled is
A lean, self-modifying coding/building agent (Claude Code spirit) built on the
Hermes engine, keeping Hermes' three strengths — skills (self-improvement),
memory, identity — with everything else stripped or dormant. Model switchable
from day one (OpenRouter first; provider-agnostic).

## Design decisions (user-confirmed 2026-10-31)
- Path: fork Hermes source, strip + strengthen. NOT stock-Hermes profile, NOT from scratch.
- Interface: terminal/CLI only. No Telegram, no desktop app, no connectors.
- Job: building things — websites, AI business, code. All-round assistant second.
- Name: "Untitled".
- Self-modification: FULL freedom — Untitled may edit its own source, not just config/skills/tools.
- Distribution: Untitled is published like Hermes — anyone can use it. The repo must stay
  generic: no personal paths, identities, or user-specific config in repo code; those
  belong in each user's own profile (SOUL.md, memory, .env).

## Strip list (make dormant or delete)
- node_modules/, website/, apps/, ui-tui/, web/, tui_gateway/, contributors/ (already removed from tree)
- All chat channels except CLI: telegram, discord, slack, whatsapp, etc. (gateway multiplexing)
- Hosted connectors / MCP catalog auto-setup
- Cron (no always-on channel to deliver to)
- Pets/dashboard/games and similar surface
- Trading plugins

## Keep & strengthen
1. Identity — SOUL.md as the single voice; Untitled owns rewriting it (with a changelog trail).
2. Memory — persistent notes + session search; make consolidation routine (auto-summarize + prune).
3. Skills — self-improvement loop: Untitled writes/updates its own skills after tasks; no approval gate
   (user granted full freedom), but every skill edit is logged and revertible via git.
4. Coding tools — Claude Code-style: strong file edit/search, terminal, plan-then-build habits.
5. Self-tweak layer — Untitled can modify its own source; changes land in git so user reviews via history.

## Milestones
- M1 (done): fork boots CLI, chats with real model (OpenRouter key), model switchable.
- M2 (done 2026-10-31): stripped at code level — removed gateway/, all platform chat
  plugins (telegram, discord, slack, …), UI/docs surface (apps, website, web, ui-tui,
  tui_gateway, contributors, locales, assets, evals, plugin-catalog, optional-mcps,
  js tooling), and dormant built-in plugins (image/video gen, kanban, meet, teams,
  dashboard, achievements, browser, computer_use, delegation, cron_providers).
  CLI boot + one-shot chat verified after each removal stage. Config-level strip:
  profile config.yaml pins platform_toolsets.cli to coding toolsets only (terminal,
  file, web, search, vision, skills, todo), cron catch-up off, telemetry off.
  Skills pruned in the development profile to software-development / web / devops /
  autonomous-ai-agents. Identity: SOUL.md live in the development profile with changelog.
  Memory verified: agent can write MEMORY.md in its profile.
- M3 (done 2026-10-31): self-modification layer live. scripts/self_edit.py gives Untitled
  bounded, git-tracked self-edits: commit (syntax-checks py/json/yaml, refuses paths
  outside the repo, prefixes Untitled:self-edit:), revert (refuses on a dirty tree),
  log, status. Verified end-to-end: Untitled ran live, edited its own script (dirty-tree
  guard on revert), committed via the tool, exercised both revert paths, and updated
  its SOUL changelog and memory.
- M4 (done 2026-10-31): hardening.
  - Usage/cost tracking: scripts/Aa_usage.py reports sessions, api calls, token
    totals (in/out/cache/reasoning), estimated vs actual cost, per-model and
    recent-session breakdown from the profile's state.db (opened read-only via
    immutable uri so it is safe while the agent runs). Flags: --db, -n, --csv.
  - Self-edit guardrails in scripts/self_edit.py's commit path:
    1. Injection scan of every staged file via tools/threat_patterns.py —
       hard findings (prompt injection, prompt override, exfil, secrets,
       invisible unicode, …) BLOCK the commit; soft C2 hits WARN only.
    2. Test gate: source commits (agent/tools/hermes_cli/scripts/tests,
       *.py/*.sh) must pass scripts/Aa_selftest.py (compile smoke + unittest
       discovery of tests/Untitled/) before the commit sticks; nothing is left
       staged after a refusal. Non-source commits skip the gate.
  - scripts/Aa_selftest.py: stdlib-only two-layer runner (compileall +
    unittest discover tests/Untitled/); AA_GATE_RUNNING=1 gate mode; a direct run
    sets AA_SELFTEST_RUNNING so the suite's own recursion probe skips.
  - tests/Untitled/test_self_edit.py: unit tests covering path refusal, injection
    gate (payload samples — hex-escaped in source so the test file itself
    never trips the scanner; runtime strings identical), gate pass/refuse +
    no-staged-leftover assertions, non-source skip, revert dirty guard,
    script smoke tests.
  - Verified: full suite 11 tests OK (1 by-design skip); first guarded commit
    landed as 1d8997c07e "Untitled:self-edit: M4: …" with both gates exercised live
    (scanner blocked a payload-bearing test file until fixtures were
    neutralized; test gate refused the earlier bare-function probe).
- M5 (done 2026-10-31): complementary hardening.
  - Aa_memory.py: MEMORY.md consolidation to a char budget — dry-run report by
    default, --apply moves oldest entries to MEMORY-archive.md (§ separators
    preserved, last/oversized single entry never moved). Unit + CLI tests
    (tests/Untitled/test_Aa_memory.py).
  - self_edit.py "soul" subcommand: appends a dated entry under SOUL.md
    "## Changelog" and commits through the same guarded path
    (Untitled:self-edit: soul: …). First live use: f7b31cd20f.
  - Suite: 21 tests OK. Guarded commits af3d6ad68d (M5 code+tests),
    f7b31cd20f (soul).
- M6 (in progress): coding-tool strengthening. Prep survey done 2026-10-31:
  no repo-map/symbol extraction exists (edits rely on tools/file_tools.py
  patch_tool fuzzy matching); the self-edit test gate always runs the full
  suite (scripts/Aa_selftest.py: compileall + unittest discover tests/Untitled);
  scripts/Aa_usage.py already reports usage from state.db.
  Planned items:
  1. (done 2026-10-31) Repo map/symbols: scripts/Aa_repo_map.py — stdlib-only
     ast extraction of classes/functions/methods with line spans for target
     files (or a whole directory summary), so edits can be aimed at real
     symbols instead of fuzzy text; self-test gate runs it on scripts/
     (repo-map smoke step); temp test clones auto-seed scripts/Aa_*.py.
  2. (done 2026-10-31) Targeted test selection: self_edit.py gates large
     diffs (>=4 source files or >=200 added lines) to only the tests/Untitled
     modules whose text names a changed file's stem, plus byte-compile of
     the changed files; small diffs still run the full suite.
  3. (done 2026-10-31) Unused-code candidates: Aa_usage.py --unused lists
     registered tool code paths (static ast scan of registry.register calls)
     with zero recorded calls in messages.tool_name — report-only, never
     auto-removing; dynamic-registration names are a documented blind spot.
  M6 complete.

## Layout
- Repo: this checkout (branch `untitled`)
- Profile data (SOUL.md, memory, skills, sessions): lives in the Hermes profiles dir
  for the running instance — kept out of the repo (generic, user-specific data goes there)
- Env: run-in-hermes-env from the upstream checkout reused for Untitled's checkout too
