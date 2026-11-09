#!/bin/bash
# Aa installer for Linux - download, then run: bash Aa-install-linux.sh
echo "Downloading the Aa installer..."
curl -fsSL https://untitled-aa.pages.dev/install-aa.sh -o /tmp/aa-install.sh || { echo "Download failed - check your internet connection."; exit 1; }
bash /tmp/aa-install.sh
echo
echo "Install finished. If it says done, open a new terminal and type: hermes"
