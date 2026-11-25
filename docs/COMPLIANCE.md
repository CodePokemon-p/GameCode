# GameCode: Requirement Compliance Matrix

| # | Requirement | Status | How it is met / why not |
|---|-------------|--------|-------------------------|
| 1 | Fork OpenCode + replace branding | Skipped (assumption) | Built as a standalone Textual app, branded "GameCode". |
| 2 | 5 primary agents + subagents | Done (partly) | 5 primary agents, each with its own default model and an encrypted subagent prompt (shown in the status bar). Subagents are not called yet. |
| 3 | Model anonymization + outside-provider model | Done | No model or provider name is shown in the UI. Groq is the outside provider; all five agents use it. |
| 4 | Per-agent system prompts | Done | Each agent has its own prompt, stored encrypted. |
| 5 | Prompt protection | Done | AES-256-GCM, decrypted on demand, cleared on agent switch. |
| 6 | Context hand-off via .md | Done | Every switch writes a numbered .md file in `handoffs/`. |
| 7 | Guardrails | Done | Injection defense, off-topic and language scope, plan-type no-edit, "What next?" enforced in code. |
| 8 | MCP servers + skills | Deferred | Documented as future work. |
| 9 | Tab-only switching, no /models | Done | Tab / F2 / Ctrl+T switch agents; there is no /models command. |
| 10 | API key gating | Done | Invalid or missing key gives Locked Mode (Build + Plan only). |
| 11 | License expires after 2 days | Done | Verified by tests; expired license disables all agents. |
| 12 | Windows installer + uninstaller | Done | Inno Setup `GameCode-Setup.exe`; uninstall removes app data. |
| 13 | Documentation | Done | This file, README, architecture and demo script. |

## Notes and assumptions
- The LLM layer uses a Mock client by default. `OpenCodeZenLLM` targets `https://opencode.ai/zen/v1` (set `GAMECODE_USE_LIVE_LLM=1` with a real key). Tested with a real key: authentication worked, but Zen's free usage limit (FreeUsageLimitError) blocked live replies, so the demo uses the mock.
- Each agent has an encrypted subagent prompt (Agent1a to Agent5a), but the pipeline does not call subagents yet.
- Any key starting with `sk-` and at least 20 characters is accepted as well-formed.
- 
## Assumptions and known gaps (against the PDF)
- **Req 1 (fork OpenCode):** built as a standalone Python/Textual app instead of a fork, so there was no OpenCode branding to replace. The app is branded "GameCode" throughout.
- **Req 2 (per-agent default models):** each agent has its own default model (a router in `llm.py`). Because Zen's free limit blocked live requests, all five models are served by Groq instead of Zen free models. The Zen client is implemented but not used in the demo. Subagent prompts exist but subagents are not called yet.
- **Req 3 (anonymization):** model and provider names are never shown in the UI, and error messages only say "LLM". Groq is the outside provider (OpenRouter was not used).
- **Req 6 (hand-off):** hand-off `.md` files are written by the app on every agent switch. Agents do not yet generate `.md` files themselves.
- **Req 8 (MCP and skills):** not implemented. No skills from a public GitHub repo were imported.
- **Req 10 (API key):** a dedicated OpenCode workspace and API key were created. The key authenticated against `https://opencode.ai/zen/v1`, but Zen returned `FreeUsageLimitError` for live requests.
- **Req 12 (dependencies):** Python and all pip packages are bundled inside the PyInstaller build, so the installer needs no separate Python. `graphifyy` is not used.