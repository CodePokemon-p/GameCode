"""Tests for .md context hand-off serialization."""
from pathlib import Path

import pytest

from gamecode.handoff import HandoffContext, HandoffManager, TranscriptEntry


@pytest.fixture
def mgr(tmp_path: Path) -> HandoffManager:
    return HandoffManager(tmp_path / "handoffs")


def _ctx(summary="", transcript=None, open_tasks=None) -> HandoffContext:
    return HandoffContext(
        session_id="session_test",
        from_agent="Agent1",
        from_agent_name="C++ Orchestrator",
        to_agent="Agent2",
        to_agent_name="C# Architect",
        transcript=transcript or [],
        open_tasks=open_tasks or [],
        summary=summary,
    )


class TestHandoffWrite:
    def test_creates_md_file(self, mgr):
        path = mgr.write(_ctx())
        assert path.exists()
        assert path.suffix == ".md"

    def test_filename_includes_from_to_and_sequence(self, mgr):
        path = mgr.write(_ctx())
        assert path.name == "001_Agent1_to_Agent2.md"

    def test_session_folder_created(self, mgr):
        path = mgr.write(_ctx())
        assert path.parent.name == "session_test"

    def test_contains_header_and_agents(self, mgr):
        text = mgr.write(_ctx()).read_text(encoding="utf-8")
        assert "# Context Hand-off" in text
        assert "C++ Orchestrator" in text
        assert "C# Architect" in text
        assert "Agent1" in text and "Agent2" in text

    def test_contains_summary(self, mgr):
        text = mgr.write(_ctx(summary="Working on C++ linked list")).read_text()
        assert "Working on C++ linked list" in text

    def test_contains_transcript(self, mgr):
        transcript = [
            TranscriptEntry("user", "Write a C++ hello world"),
            TranscriptEntry("agent", "Done. What next?"),
        ]
        text = mgr.write(_ctx(transcript=transcript)).read_text()
        assert "Write a C++ hello world" in text
        assert "Done. What next?" in text

    def test_contains_open_tasks(self, mgr):
        text = mgr.write(_ctx(open_tasks=["Refactor to smart pointers"])).read_text()
        assert "- [ ] Refactor to smart pointers" in text

    def test_sequence_numbers_increment(self, mgr):
        p1 = mgr.write(_ctx())
        p2 = mgr.write(_ctx())
        assert p1.name.startswith("001_")
        assert p2.name.startswith("002_")


class TestHandoffRead:
    def test_read_existing(self, mgr):
        path = mgr.write(_ctx())
        assert "# Context Hand-off" in mgr.read(path)

    def test_read_missing_returns_empty(self, mgr):
        assert mgr.read(Path("/never/created.md")) == ""

    def test_list_for_session(self, mgr):
        mgr.write(_ctx())
        mgr.write(_ctx())
        assert len(mgr.list_for_session("session_test")) == 2

    def test_list_for_unknown_session(self, mgr):
        assert mgr.list_for_session("nonexistent") == []

    def test_read_latest(self, mgr):
        mgr.write(_ctx(summary="first"))
        mgr.write(_ctx(summary="second"))
        latest = mgr.read_latest("session_test")
        assert latest is not None and "second" in latest

    def test_read_latest_empty(self, mgr):
        assert mgr.read_latest("no_session") is None