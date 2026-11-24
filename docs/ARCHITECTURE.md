# GameCode: Architecture

## Overview
GameCode is a standalone Windows terminal app (Python + Textual) with a
5-agent pipeline for C++ and C# work. Agents are locked down by encryption,
guardrails, an API key gate and a license expiry.

## Modules (src/gamecode)
| Module | Responsibility |
|--------|----------------|
| `tui.py` | Textual UI, API key modal, locked/unlocked boot, agent switching |
| `agents.py` | 5 agent specs, `AgentManager`, `Guardrail` checks, "What next?" enforcement |
| `guardrails.py` | Language patterns (C++ / C#) used for per-agent scope |
| `security.py` | `AES256Cipher`, key derivation, `PromptStore`, `LicenseManager` |
| `handoff.py` | Writes and reads numbered `.md` hand-off files |
| `config.py` | Saves and loads the API key, checks key format |
| `llm.py` | `LLMClient` interface, `MockLLM`, `OpenCodeZenLLM` |

## Request flow
1. User types a message in the TUI.
2. `Guardrail.check` runs first (injection, off-topic, language scope, plan-type no-edit).
3. If allowed, `AgentManager` decrypts only the active agent's prompt.
4. The prompt and message go to the LLM client (Mock by default).
5. The reply always ends with "What next?".

## Security design
- **Prompts at rest:** AES-256-GCM, so tampering is detected.
- **Prompts in memory:** decrypted on demand and cleared when the agent switches.
- **Injection defense (layered):** handles typos, leetspeak, Cyrillic look-alikes,
  base64/hex payloads, role-change phrases and chat-template tokens.
- **API key gate:** no valid key means Locked Mode (Build + Plan only, no custom prompts).
- **License:** expires 2 days after first run; once expired, all agents are disabled.

## Modes
- **Unlocked:** 5 agents, encrypted prompts, hand-off files.
- **Locked:** Build and Plan placeholders only. Guardrails and license still apply.

## Data location
Everything is stored in `%APPDATA%\GameCode` (licenses, prompts, handoffs,
config.json). Override with the `GAMECODE_HOME` environment variable.

## Packaging
PyInstaller builds a one-folder app (`installer/build_exe.ps1`). Inno Setup
wraps it as `GameCode-Setup.exe` (`installer/GameCode.iss`), with an API key
page and an uninstaller that removes app data.

## Known limitations
- The API key is checked for format only (`sk-` plus 20 characters or more), not against a server.
- `config.json` stores the key in plain text; production should use Windows DPAPI.
- The license is a local file; a determined user with local access could reset it.
  Production would need a server-side check.
- The LLM is a Mock by default. `OpenCodeZenLLM` exists, but its base URL is
  unverified and it has not been tested with a real key.
- OpenCode fork, model anonymization, MCP servers and skills are deferred (see COMPLIANCE.md).