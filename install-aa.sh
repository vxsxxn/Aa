#!/bin/bash
# Aa Desktop — one-file installer for macOS / Linux.
# Usage:  bash install-aa.sh
set -euo pipefail

REPO_URL="https://github.com/vxsxxn/Aa.git"
BRANCH="aa"
DEST="${HOME}/aa"

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }

say "Aa Desktop installer"

# 1. Check prerequisites -------------------------------------------------
if ! command -v git >/dev/null 2>&1; then
  echo "git is required. On macOS run:  xcode-select --install   (then re-run this script)"
  exit 1
fi
if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required (it ships with macOS; on Linux install it with your package manager)."
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

# 3. Make sure uv is available -------------------------------------------
# uv sets up the Python environment; it can even fetch Python itself.
if ! command -v uv >/dev/null 2>&1; then
  say "Installing uv (small, local, user-level)"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

# 4. Set up Python environment -------------------------------------------
say "Setting up (first run downloads Python + packages — may take a few minutes)"
cd "$DEST"
uv sync --frozen

# 5. Launch ---------------------------------------------------------------
say "Starting Aa Desktop (your browser will open — paste your OpenRouter API key in ⚙ Settings)"
exec uv run --frozen scripts/Aa_desktop.py
