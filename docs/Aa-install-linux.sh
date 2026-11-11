#!/bin/bash
# Untitled installer for Linux - download, then run: bash Untitled-install-linux.sh
echo "Downloading the Untitled installer..."
curl -fsSL https://untitled-untitled.pages.dev/install-untitled.sh -o /tmp/untitled-install.sh || { echo "Download failed - check your internet connection."; exit 1; }
bash /tmp/untitled-install.sh
echo
echo "Install finished. If it says done, open a new terminal and type: hermes"
