# GameCode

A locked-down 5-agent coding assistant (C++ / C#) built for the
Infotainment Academy **AI/Prompt Engineer** test task.

Built as a standalone **Python + Textual TUI** — not a fork of
OpenCode's TypeScript monorepo — per HR's clarification that the
Core Requirements are the essential criteria and Bonus Features
are for differentiation.

## Status

- [x] **Phase 1a** — Scaffolding
- [ ] **Phase 1b** — AES-256-GCM encryption, persistent 2-day license, encrypted prompt store
- [ ] **Phase 1c** — 5-agent pipeline + guardrails
- [ ] **Phase 1d** — Test suite
- [ ] **Phase 2** — Textual TUI + `.md` context hand-off on Tab
- [ ] **Phase 3** — API key gating
- [ ] **Phase 4** — Windows `.exe` installer + uninstaller
- [ ] **Phase 5** — Documentation (`docs/COMPLIANCE.md`, `docs/ARCHITECTURE.md`) + demo

## Requirements covered

**Core:** 5-agent architecture · AES-256-GCM prompt encryption (on-demand decrypt, clear on switch) · comprehensive guardrails · `.md` context hand-off on Tab · 2-day license expiry (persisted).

**Bonus:** Textual TUI · API key gating · Windows installer/uninstaller.

## Quick start (dev)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pytest