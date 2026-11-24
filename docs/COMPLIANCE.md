# GameCode: Requirement Compliance Matrix

| # | Requirement | Status | How it is met / why not |
|---|-------------|--------|-------------------------|
| 1 | Fork OpenCode + replace branding | Skipped (assumption) | Built as a standalone Textual app, branded "GameCode". |
| 2 | 5 primary agents + subagents | Done | 5 primary agents, each with a subagent (shown in the status bar). |
| 3 | Model anonymization + OpenRouter model | Deferred | No model names are shown anywhere in the UI. |
| 4 | Per-agent system prompts | Done | Each agent has its own prompt, stored encrypted. |
| 5 | Prompt protection | Done | AES-256-GCM, decrypted on demand, cleared on agent switch. |
| 6 | Context hand-off via .md | Done | Every switch writes a numbered .md file in `handoffs/`. |
| 7 | Guardrails | Done | Injection defense, off-topic and language scope, plan-type no-edit, "What next?" enforced in code. |
| 8 | MCP servers + skills | Deferred | Documented as future work. |
| 9 | Tab-only switching, no /models | Done | Tab / F2 / Ctrl+T switch agents; there is no /models command. |
| 10 | API key gating | Done | Invalid or missing key gives Locked Mode (Build + Plan only). |
| 11 | License expires after 2 days | Done | Verified by tests; expired license disables all agents. |
| 12 | Windows installer + uninstaller | Done | Inno Setup `GameCode-Setup.exe`; uninstall removes app data. |
| 13 | Documentation | In progress | This file, plus architecture and demo script. |

## Notes and assumptions
- The LLM layer uses a Mock client by default; `OpenCodeZenLLM` is implemented for live use (set `GAMECODE_USE_LIVE_LLM=1` with a real key).
- Any key starting with `sk-` and at least 20 characters is accepted as well-formed.