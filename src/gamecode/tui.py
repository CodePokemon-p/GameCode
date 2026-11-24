"""
tui.py — Textual UI with lock screen, API key gating, and context hand-off.

Two modes:
  * unlocked — full 5-agent pipeline, encrypted prompts, hand-off files
  * locked   — only Build + Plan placeholder agents (no encryption, no custom work)
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Input, Label, Markdown, Static

from .agents import AgentManager, Guardrail
from .config import Config
from .handoff import HandoffContext, HandoffManager, TranscriptEntry
from .llm import make_client

DEFAULT_API_KEY_ENV = "GAMECODE_API_KEY"

LOCKED_AGENTS = {
    "Build": {"can_edit": True,  "kind": "build-type"},
    "Plan":  {"can_edit": False, "kind": "plan-type"},
}


class ApiKeyScreen(ModalScreen[str | None]):
    """Startup modal. Returns the entered key (unlock) or None (locked mode)."""

    CSS = """
    ApiKeyScreen { align: center middle; }
    #dialog {
        width: 72;
        height: auto;
        border: thick $primary;
        padding: 1 2;
        background: $panel;
    }
    #dialog Label { margin: 1 0 0 0; }
    #dialog Input { margin: 0 0 1 0; }
    #dialog Horizontal { align: center middle; height: 3; }
    #dialog Button { margin: 0 1; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="dialog"):
            yield Label("🔑 Enter your OpenCode Zen API key (starts with sk-):")
            yield Input(
                placeholder="sk-...",
                password=True,
                id="api-key-input",
            )
            yield Label(
                "Leave empty and press 'Locked Mode' for Build + Plan only.",
                id="hint",
            )
            with Horizontal():
                yield Button("Unlock", variant="primary", id="unlock-btn")
                yield Button("Locked Mode", id="locked-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "unlock-btn":
            key = self.query_one("#api-key-input", Input).value.strip()
            self.dismiss(key if key else None)
        else:
            self.dismiss(None)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        key = event.value.strip()
        self.dismiss(key if key else None)


class GameCodeApp(App):
    CSS = """
    Screen { background: $surface; }
    #status-bar {
        height: 3;
        padding: 0 1;
        content-align: left middle;
        text-style: bold;
    }
    #status-bar.plan-type  { background: $warning 30%; }
    #status-bar.build-type { background: $success 30%; }
    #status-bar.locked     { background: $error 60%; }
    #chat-log {
        height: 1fr;
        border: round $primary;
        padding: 0 1;
        overflow-y: auto;
    }
    #user-input { dock: bottom; }
    """

    BINDINGS = [
        Binding("f2", "switch_agent", "Switch Agent (F2)", priority=True, show=True),
        Binding("ctrl+t", "switch_agent", "Switch (Ctrl+T)", priority=True, show=True),
        Binding("ctrl+q", "quit", "Quit", show=True),
    ]

    def __init__(
        self,
        api_key: str | None = None,
        base_dir: Path | str | None = None,
        config_dir: Path | str | None = None,
        skip_modal: bool = False,
    ):
        super().__init__()
        self._skip_modal = skip_modal
        self.base_dir = Path(base_dir) if base_dir else Path.cwd()
        self.config = Config(config_dir or self.base_dir / "userdata")
        self._explicit_key = api_key
        self._locked_mode = False
        self._locked_agent = "Build"
        self._message_lines: list[str] = []
        self._locked_license = None
        self._locked_encrypted = False
        self.session_id = datetime.now(timezone.utc).strftime("session_%Y%m%d_%H%M%S")
        self.transcript: list[TranscriptEntry] = []
        self.agent_mgr: AgentManager | None = None
        self.handoff_mgr = HandoffManager(self.base_dir / "handoffs")
        self._license_mgr = None
        self._init_key = api_key

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="status-bar")
        yield Markdown("", id="chat-log")
        yield Input(
            placeholder="Type here and press Enter… (F2 / Ctrl+T to switch agent)",
            id="user-input",
        )
        yield Footer()

    # ---- startup ---------------------------------------------------------
    def on_mount(self) -> None:
        self.title = "GameCode"
        self.sub_title = self.session_id

        env_key = os.getenv(DEFAULT_API_KEY_ENV)
        key = env_key or self._explicit_key or self.config.load_api_key()
        if key and Config.validate_format(key):
            self._boot_unlocked(key)
        elif self._skip_modal:
            self._boot_locked()
        else:
            self.push_screen(ApiKeyScreen(), callback=self._on_key_submitted)

    def _on_key_submitted(self, key: str | None) -> None:
        if key and Config.validate_format(key):
            self.config.save_api_key(key)
            self._boot_unlocked(key)
        else:
            self._boot_locked()

    # ---- unlocked boot ---------------------------------------------------
    def _boot_unlocked(self, api_key: str) -> None:
        self._init_key = api_key
        llm = make_client(api_key)
        self.agent_mgr = AgentManager(
            api_key,
            prompts_dir=self.base_dir / "prompts",
            license_dir=self.base_dir / "licenses",
            llm_client=llm,
        )
        self._license_mgr = self.agent_mgr.license

        status = self.agent_mgr.license.status()
        if not status["valid"]:
            self._lock_license_expired(status)
            return

        try:
            self.agent_mgr.activate_initial()
        except Exception as e:
            self._log(f"⚠️ Could not load encrypted prompts: {e}")
            self._log("_Falling back to Locked Mode._")
            self._boot_locked()
            return

        self._refresh_status_bar()
        self._log(
            f"**GameCode ready** — license valid, "
            f"{status['days_remaining']} day(s) remaining."
        )
        self._log(
            "_Unlocked mode: 5-agent pipeline, encrypted prompts, .md hand-off. "
            "Press **F2** (or **Ctrl+T**) to switch agent._"
        )
        self.set_timer(0.1, self._focus_input)

    # ---- locked boot -----------------------------------------------------
    def _boot_locked(self) -> None:
        self._locked_mode = True
        self._locked_agent = "Build"
        # Create a license manager so the license requirement still applies
        from .security import LicenseManager
        self._license_mgr = LicenseManager(
            "sk-gamecode-locked-mode",
            self.base_dir / "licenses",
        )

        status = self._license_mgr.status()
        if not status["valid"]:
            self._lock_license_expired(status)
            return

        self._refresh_status_bar()
        self._log(
            "**🔒 Locked Mode** — no API key configured."
        )
        self._log(
            "_Only **Build** and **Plan** placeholder agents are available. "
            "Your encrypted 5-agent pipeline is not loaded. "
            "Enter a valid `sk-` key in `%APPDATA%\\GameCode\\config.json` "
            "or set `GAMECODE_API_KEY` and restart to unlock._"
        )
        self._log("_Press F2 / Ctrl+T to toggle Build ↔ Plan._")
        self.set_timer(0.1, self._focus_input)

    def _lock_license_expired(self, status: dict) -> None:
        self._locked_mode = True
        bar = self.query_one("#status-bar", Static)
        bar.update(f"⛔ LICENSE EXPIRED ({status['expiry_date']}) — all agents disabled.")
        bar.add_class("locked")
        inp = self.query_one("#user-input", Input)
        inp.disabled = True
        inp.placeholder = "License expired"
        self._log("⛔ **License expired.** All agents, prompts, and tools are disabled.")

    # ---- shared ----------------------------------------------------------
    def _focus_input(self) -> None:
        try:
            self.query_one("#user-input", Input).focus()
        except Exception:
            pass

    def on_click(self) -> None:
        self._focus_input()

    def on_key(self, event) -> None:
        if event.key == "tab":
            event.prevent_default()
            event.stop()
            self.action_switch_agent()

    def _log(self, md_text: str) -> None:
        self._message_lines.append(md_text)
        joined = "\n\n---\n\n".join(self._message_lines)
        md = self.query_one("#chat-log", Markdown)
        md.update(joined)
        try:
            md.scroll_end(animate=False)
        except Exception:
            pass

    def _record(self, role: str, text: str) -> None:
        self.transcript.append(TranscriptEntry(role=role, text=text))

    def _refresh_status_bar(self) -> None:
        bar = self.query_one("#status-bar", Static)
        bar.remove_class("plan-type", "build-type", "locked")
        if self._locked_mode:
            kind = LOCKED_AGENTS[self._locked_agent]["kind"]
            icon = "🔒"
            bar.add_class(kind)
            bar.update(
                f"🔒 {self._locked_agent} ({kind}) · Locked Mode · no key"
            )
        else:
            spec = self.agent_mgr.current_spec
            kind = "plan-type" if not spec.can_edit_files else "build-type"
            bar.add_class(kind)
            icon = "📋" if not spec.can_edit_files else "🛠"
            langs = "/".join(l.upper() for l in spec.allowed_languages)
            bar.update(
                f"▶ {spec.role.value} · {spec.display_name} ({kind}, {langs}) {icon}   "
                f"subagent: {spec.subagent_name}"
            )

    # ---- input -----------------------------------------------------------
    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.input.value.strip()
        event.input.value = ""
        self._handle_user_message(text)

    def _handle_user_message(self, text: str) -> None:
        if not text:
            return
        if self._locked_mode:
            self._handle_locked_message(text)
            return
        if self.agent_mgr is None:
            return

        self._log(f"**🧑 You:**\n\n{text}")
        self._record("user", text)
        result = self.agent_mgr.process(text)
        if not result.allowed:
            self._log(f"**🛡️ Guardrail:**\n\n{result.response}")
            return
        self._log(f"**🤖 {result.display_name}:**\n\n{result.response}")
        self._record("agent", result.response)

    def _handle_locked_message(self, text: str) -> None:
        # License still gates locked mode
        if self._license_mgr and not self._license_mgr.is_valid():
            self._log("⛔ **License expired.** No agents available.")
            return

        self._log(f"**🧑 You:**\n\n{text}")
        self._record("user", text)

        can_edit = LOCKED_AGENTS[self._locked_agent]["can_edit"]
        guard = Guardrail.check(text, can_edit_files=can_edit)
        if not guard.allowed:
            self._log(f"**🛡️ Guardrail:**\n\n{guard.reason}")
            return

        self._log(
            f"**🤖 {self._locked_agent} (locked):**\n\n"
            f"_[Locked mode — encrypted pipeline not available.]_\n\n"
            f"Processing: `{text}`\n\nWhat next?"
        )
        self._record("agent", f"[Locked/{self._locked_agent}] {text}")

    # ---- switch ----------------------------------------------------------
    def action_switch_agent(self) -> None:
        if self._locked_mode:
            if self._license_mgr and not self._license_mgr.is_valid():
                return
            self._locked_agent = "Plan" if self._locked_agent == "Build" else "Build"
            self._log(
                f"**🔒 Switched (Locked Mode):** → **{self._locked_agent}**"
            )
            self._refresh_status_bar()
            self._focus_input()
            return

        if self.agent_mgr is None:
            return

        from_role = self.agent_mgr.current_agent
        from_spec = self.agent_mgr.current_spec
        to_role = self.agent_mgr.switch_to_next()
        to_spec = self.agent_mgr.current_spec

        ctx = HandoffContext(
            session_id=self.session_id,
            from_agent=from_role.value,
            from_agent_name=from_spec.display_name,
            to_agent=to_role.value,
            to_agent_name=to_spec.display_name,
            transcript=list(self.transcript),
            open_tasks=[],
            summary=(
                f"{from_spec.display_name} handed off "
                f"{len(self.transcript)} message(s) to {to_spec.display_name}."
            ),
        )
        path = self.handoff_mgr.write(ctx)

        self._log(
            f"**↪ Context Hand-off**\n\n"
            f"`{from_role.value}` → `{to_role.value}`  \n"
            f"_{len(ctx.transcript)} message(s) captured_  \n"
            f"_File: `{path.name}`_"
        )

        self.transcript.clear()
        self._refresh_status_bar()
        self._focus_input()


def main() -> None:
    api_key = os.getenv(DEFAULT_API_KEY_ENV)
    GameCodeApp(api_key=api_key).run()


if __name__ == "__main__":
    main()