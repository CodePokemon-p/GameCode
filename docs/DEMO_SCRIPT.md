# GameCode: Demo Script (about 5-6 minutes)

## Before recording
- Uninstall any old GameCode and delete `%APPDATA%\GameCode`.
- Have `installer_output\GameCode-Setup.exe` ready.
- Terminal open in the project folder, window large and readable.

## 1. Intro (20 sec)
Say: GameCode is a locked-down 5-agent C++/C# coding assistant for Windows,
with encrypted prompts, guardrails, API key gating and a 2-day license.

## 2. Tests (30 sec)
Run `pytest` and show the green result (133 passed).

## 3. Install (60 sec)
- Run `GameCode-Setup.exe`. Choose a folder such as `D:\Apps\GameCode`.
- Show the API Key page. Leave it blank first to demo Locked Mode.
- Finish with "Launch GameCode" ticked.

## 4. Locked Mode (45 sec)
- Show the red "Locked Mode" status bar.
- Press F2: Build and Plan toggle. Only these two exist.
- Type `What's the weather` and show the guardrail block.

## 5. Unlocked Mode (90 sec)
- Close the app. Set a test key and start it:
  `$env:GAMECODE_API_KEY="sk-test-key-1234567890abc"` then run `GameCode.exe`.
- Show the 5-agent status bar (Agent1, C++ Orchestrator, subagent shown).
- Type `Write a C++ linked list`: reply ends with "What next?".
- Press Tab to Agent2 (C# only), type `Write a C++ linked list`:
  blocked by per-agent scope.
- Type `ignore previous instructions`: blocked as injection.
- Press Tab through the agents and show the `.md` files in
  `%APPDATA%\GameCode\handoffs\<session>`. Open one.

## 6. Security (45 sec)
- Show the `prompts` folder in `%APPDATA%\GameCode`: files are unreadable (AES-256-GCM).
- Run `pytest tests/test_tui.py::test_expired_license_locks_app -v`
  to show that an expired license disables everything.

## 7. Uninstall (30 sec)
- Settings > Apps > GameCode > Uninstall.
- Run `Test-Path $env:APPDATA\GameCode` and show `False`.

## 8. Wrap-up (20 sec)
Show `docs/COMPLIANCE.md` and say what was deferred (OpenCode fork, MCP,
model anonymization) and why. Mention the Mock LLM and that
`OpenCodeZenLLM` is ready for a real key.