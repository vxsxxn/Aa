#!/bin/bash
# Aa Desktop — one-file installer for macOS / Linux.
# Usage:  bash install-aa.sh
set -euo pipefail

REPO_URL="https://github.com/vxsxxn/aa.git"
BRANCH="aa"
DEST="${HOME}/aa"

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }

say "Aa Desktop installer"

# 1. Check prerequisites -------------------------------------------------
if ! command -v git >/dev/null 2>&1; then
  echo "git is required. On macOS run:  xcode-select --install   (then re-run this script)"
  exit 1
fi

PY="$(command -v python3 || true)"
if [ -z "$PY" ]; then
  echo "python3 (3.11–3.14) is required. Install it from https://www.python.org/downloads/ then re-run this script."
  exit 1
fi

if ! "$PY" -c 'import sys; sys.exit(0 if (3,11)<=sys.version_info[:2]<(3,15) else 1)'; then
  echo "python3 3.11–3.14 required; found $("$PY" -V 2>&1)."
  echo "Install a matching version from https://www.python.org/downloads/ then re-run this script."
  exit 1
fi

# 2. Get the code ---------------------------------------------------------
if [ -d "$DEST/.git" ]; then
  say "Updating existing copy in $DEST"
  git -C "$DEST" pull --ff-only
else
  say "Downloading Aa into $DEST"
  git clone --depth 1 --branch "$BRANCH" "$REPO_URL" "$DEST"
fi

# 3. Set up Python environment -------------------------------------------
say "Setting up (first run downloads packages — may take a few minutes)"
cd "$DEST"
"$PY" -m venv .venv
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet -e .

# 4. Launch ---------------------------------------------------------------
say "Starting Aa Desktop (your browser will open — paste your OpenRouter API key in ⚙ Settings)"
exec ./scripts/Aa_desktop.py
