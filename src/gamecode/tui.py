"""
tui.py — Textual UI with Tab-driven context hand-off.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, Input, Markdown, Static

from .agents import AgentManager
from .handoff import HandoffContext, HandoffManager, TranscriptEntry

DEFAULT_API_KEY_ENV = "GAMECODE_API_KEY"


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

    def __init__(self, api_key: str, base_dir: Path | str | None = None):
        super().__init__()
        self.api_key = api_key
        base = Path(base_dir) if base_dir else Path.cwd()
        self.agent_mgr = AgentManager(
            api_key,
            prompts_dir=base / "prompts",
            license_dir=base / "licenses",
        )
        self.handoff_mgr = HandoffManager(base / "handoffs")
        self.session_id = datetime.now(timezone.utc).strftime("session_%Y%m%d_%H%M%S")
        self.transcript: list[TranscriptEntry] = []
        self._message_lines: list[str] = []
        self._locked = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("", id="status-bar")
        yield Markdown("", id="chat-log")
        yield Input(
            placeholder="Type here and press Enter… (F2 / Ctrl+T to switch agent)",
            id="user-input",
        )
        yield Footer()

    def on_mount(self) -> None:
        self.title = "GameCode"
        self.sub_title = self.session_id

        status = self.agent_mgr.license.status()
        if not status["valid"]:
            self._locked = True
            bar = self.query_one("#status-bar", Static)
            bar.update(f"⛔ LICENSE EXPIRED ({status['expiry_date']}) — disabled.")
            bar.add_class("locked")
            inp = self.query_one("#user-input", Input)
            inp.disabled = True
            inp.placeholder = "License expired"
            self._log("⛔ **License expired.** Reinstall or renew to continue.")
            return

        self.agent_mgr.activate_initial()
        self._refresh_status_bar()
        self._log(
            f"**GameCode ready** — license valid, "
            f"{status['days_remaining']} day(s) remaining."
        )
        self._log(
            "_Type a message and press Enter. "
            "Press **F2** (or **Ctrl+T** / **Tab**) to switch agent._"
        )
        self.set_timer(0.1, self._focus_input)

    def _focus_input(self) -> None:
        if self._locked:
            return
        try:
            self.query_one("#user-input", Input).focus()
        except Exception:
            pass

    def on_click(self) -> None:
        self._focus_input()

    def on_key(self, event) -> None:
        """Tab fallback: some terminals bypass BINDINGS but still deliver
        Key events. Only intercept if bindings did not already consume it."""
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
        spec = self.agent_mgr.current_spec
        bar = self.query_one("#status-bar", Static)
        bar.remove_class("plan-type", "build-type", "locked")
        kind = "plan-type" if not spec.can_edit_files else "build-type"
        bar.add_class(kind)
        icon = "📋" if not spec.can_edit_files else "🛠"
        langs = "/".join(l.upper() for l in spec.allowed_languages)
        bar.update(
            f"▶ {spec.role.value} · {spec.display_name} ({kind}, {langs}) {icon}   "
            f"subagent: {spec.subagent_name}"
        )

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.input.value.strip()
        event.input.value = ""
        self._handle_user_message(text)

    def _handle_user_message(self, text: str) -> None:
        if self._locked or not text:
            return

        self._log(f"**🧑 You:**\n\n{text}")
        self._record("user", text)

        result = self.agent_mgr.process(text)
        if not result.allowed:
            self._log(f"**🛡️ Guardrail:**\n\n{result.response}")
            return
        self._log(f"**🤖 {result.display_name}:**\n\n{result.response}")
        self._record("agent", result.response)

    def action_switch_agent(self) -> None:
        if self._locked:
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
    api_key = os.getenv(DEFAULT_API_KEY_ENV) or "sk-gamecode-demo-key"
    GameCodeApp(api_key=api_key).run()


if __name__ == "__main__":
    main()