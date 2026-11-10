Aa - Mac installer
==================

If double-clicking gives an error, use this instead:

1. Open Terminal (press Cmd+Space, type Terminal, press Return)
2. Type exactly:  bash ~/Downloads/Aa-install-mac.command
3. Press Return and wait for it to finish

Why the errors happen: macOS only allows software signed by a paid Apple
developer account. This installer is a plain script, so macOS blocks the
double-click and strips its execute permission. It is not malware - you
can open the file and read it. The command in step 2 runs it directly.

After it finishes, open a new Terminal window and type: hermes
