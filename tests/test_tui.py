"""Tests for the Textual TUI using Textual's pilot."""
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from gamecode.security import LicenseManager
from gamecode.tui import GameCodeApp

VALID_KEY = "sk-test-key-1234567890abc"


@pytest.fixture
def app(tmp_path: Path) -> GameCodeApp:
    """Boots directly into unlocked mode (valid explicit key)."""
    return GameCodeApp(
        api_key=VALID_KEY,
        base_dir=tmp_path,
        config_dir=tmp_path / "cfg",
    )


async def test_app_mounts(app):
    async with app.run_test():
        assert app.query_one("#user-input") is not None
        assert app.query_one("#chat-log") is not None
        assert app.query_one("#status-bar") is not None


async def test_starts_on_agent1(app):
    async with app.run_test():
        assert app.agent_mgr is not None
        assert app.agent_mgr.current_agent.value == "Agent1"
        assert app._locked_mode is False


async def test_tab_switches_agent_and_writes_handoff(app, tmp_path):
    async with app.run_test() as pilot:
        await pilot.press("tab")
        assert app.agent_mgr.current_agent.value == "Agent2"
        files = list((tmp_path / "handoffs" / app.session_id).glob("*.md"))
        assert len(files) == 1
        assert files[0].name == "001_Agent1_to_Agent2.md"


async def test_tab_cycles_through_all_five(app):
    async with app.run_test() as pilot:
        for expected in ["Agent2", "Agent3", "Agent4", "Agent5", "Agent1"]:
            await pilot.press("tab")
            assert app.agent_mgr.current_agent.value == expected


async def test_allowed_input_is_recorded(app):
    """Agent1 (C++) accepts a C++ plan request."""
    async with app.run_test() as pilot:
        app.query_one("#user-input").value = "Plan a C++ linked list"
        await pilot.press("enter")
        roles = [e.role for e in app.transcript]
        assert "user" in roles
        assert "agent" in roles


async def test_cross_language_blocked_on_wrong_agent(app):
    """Agent2 (C#-only) must refuse a C++ request — per-agent scope fires."""
    async with app.run_test() as pilot:
        await pilot.press("tab")  # → Agent2 (C#-only)
        app.query_one("#user-input").value = "Write a C++ linked list"
        await pilot.press("enter")
        roles = [e.role for e in app.transcript]
        assert "user" in roles
        assert "agent" not in roles   # guardrail blocked — no agent reply


async def test_guardrail_block_not_recorded_as_agent(app):
    async with app.run_test() as pilot:
        app.query_one("#user-input").value = "What's the weather"
        await pilot.press("enter")
        roles = [e.role for e in app.transcript]
        assert "user" in roles
        assert "agent" not in roles


async def test_handoff_captures_transcript(app, tmp_path):
    async with app.run_test() as pilot:
        await pilot.press("tab")  # Agent2
        app.query_one("#user-input").value = "Write a C# class"
        await pilot.press("enter")
        await pilot.press("tab")  # → Agent3

        files = sorted((tmp_path / "handoffs" / app.session_id).glob("*.md"))
        assert len(files) == 2
        text = files[1].read_text(encoding="utf-8")
        assert "Write a C# class" in text
        assert "Agent2" in text and "Agent3" in text


async def test_expired_license_locks_app(tmp_path):
    """Pre-write an expired license before app boots."""
    lic_dir = tmp_path / "licenses"
    lic_dir.mkdir(parents=True, exist_ok=True)
    lm = LicenseManager(VALID_KEY, lic_dir)
    st = lm.initialize_or_load()
    st["expiry_date"] = (
        datetime.now(timezone.utc) - timedelta(days=1)
    ).isoformat()
    lm._save(st)

    app = GameCodeApp(
        api_key=VALID_KEY,
        base_dir=tmp_path,
        config_dir=tmp_path / "cfg",
    )
    async with app.run_test() as pilot:
        assert app._locked_mode is True
        assert app.query_one("#user-input").disabled is True
        await pilot.press("f2")
        assert app.agent_mgr is None   # never booted