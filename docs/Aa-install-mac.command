#!/bin/bash
# Untitled installer for Mac - double-click this file.
cd "$(dirname "$0")" || exit 1
echo "Downloading the Untitled installer..."
curl -fsSL https://untitled-untitled.pages.dev/install-untitled.sh -o untitled-install.sh || { echo "Download failed - check your internet connection."; echo; echo "Close this window when done."; read -n 1; exit 1; }
bash untitled-install.sh
echo
echo "Install finished. If it says done, reopen Terminal and type: hermes"
echo
echo "Press any key to close this window."
read -n 1
