# Aa Desktop - one-file installer for Windows (PowerShell).
# Usage:  powershell -ExecutionPolicy Bypass -File install-aa.ps1
$ErrorActionPreference = "Stop"

$RepoUrl = "https://github.com/vxsxxn/Aa.git"
$Branch  = "aa"
$Dest    = Join-Path $HOME "aa"

Write-Host ""
Write-Host "Aa Desktop installer" -ForegroundColor Gray

# 1. Check prerequisites -------------------------------------------------
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  Write-Host "git is required. Install it with:  winget install --id Git.Git -e"
  Write-Host "(then re-open PowerShell and run this script again)"
  exit 1
}

# 2. Get the code ---------------------------------------------------------
if (Test-Path (Join-Path $Dest ".git")) {
  Write-Host ""
  Write-Host "Updating existing copy in $Dest" -ForegroundColor Gray
  git -C $Dest pull --ff-only
} else {
  Write-Host ""
  Write-Host "Downloading Aa into $Dest" -ForegroundColor Gray
  git clone --depth 1 --branch $Branch $RepoUrl $Dest
}

# 3. Make sure uv is available -------------------------------------------
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  Write-Host ""
  Write-Host "Installing uv (small, local, user-level)" -ForegroundColor Gray
  Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
  $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
}

# 4. Set up Python environment -------------------------------------------
Set-Location $Dest
Write-Host ""
Write-Host "Setting up (first run downloads Python + packages - may take a few minutes)" -ForegroundColor Gray
uv sync --frozen

# 5. Launch ---------------------------------------------------------------
Write-Host "Starting Aa Desktop (your browser will open - paste your OpenRouter API key in Settings)" -ForegroundColor Gray
uv run --frozen scripts/Aa_desktop.py
