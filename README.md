<p align="center">
  <img src="assets/banner.png" alt="Aa" width="100%">
</p>

# Aa

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License: MIT"></a>
  <a href="https://github.com/NousResearch/hermes-agent"><img src="https://img.shields.io/badge/Forked%20from-Hermes%20Agent-blueviolet?style=for-the-badge" alt="Forked from Hermes Agent"></a>
</p>

**Aa** is a lean, self-modifying coding and building agent. It runs on your computer, uses tools (files, terminal, web) to build things, remembers what it did, and can grow skills from that work — including editing its own source under git.

It is a fork of [Hermes Agent](https://github.com/NousResearch/hermes-agent) by [Nous Research](https://nousresearch.com) (MIT). Hermes is a full personal agent (messaging, desktop, connectors, always-on helpers). Aa keeps the engine strengths — skills, memory, identity — and aims at a smaller job: **build**, stay local by default, and stay yours.

The name is small on purpose. There are a lot of AI agents; this is another alternative.

---

## What Aa is for

| | |
| --- | --- |
| **Job** | Building — code, sites, tools. All-round assistant second. |
| **Interface** | Terminal / CLI first (`Aa`). |
| **Core** | Model access, tools, memory, skills loader, hooks/mods, self-edit + test gate. |
| **Skills** | Everything else is a skill: download one, or have Aa write one. |
| **Ownership** | Your machine, your data, open formats. Leave with it whenever you want. |

---

## Quick start (from this repo)

```bash
git clone https://github.com/vxsxxn/Aa.git
cd Aa
source ./activate          # or: uv sync / pip install -e .
Aa                         # interactive CLI
Aa --version               # should say: Aa v…
```

Configure a model provider (OpenRouter, OpenAI, Anthropic, local, …) the same way the Hermes engine does — `Aa model` / config under your profile home. Aa is provider-agnostic from day one.

```bash
Aa                  # Interactive CLI
Aa model            # Choose provider / model
Aa tools            # Configure tools
Aa doctor           # Diagnose issues
```

---

## Attribution

Aa includes code from **Hermes Agent** by **Nous Research**, licensed under the MIT License. See [LICENSE](LICENSE). Upstream project: [NousResearch/hermes-agent](https://github.com/NousResearch/hermes-agent).

This repository is **not** the upstream Hermes distribution. Install URLs, Discord, and “Built by Nous Research” branding for Hermes itself live with the [upstream project](https://hermes-agent.nousresearch.com/).

---

## License

MIT — see [LICENSE](LICENSE).
