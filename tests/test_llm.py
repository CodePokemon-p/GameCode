"""Tests for MockLLM and OpenCodeZenLLM response shaping."""
import pytest

from gamecode.llm import LLMClient, MockLLM, OpenCodeZenLLM, make_client


class TestMockLLM:
    def test_returns_string(self):
        out = MockLLM().complete("You are the C++ Orchestrator.", "Write linked list")
        assert isinstance(out, str) and len(out) > 0

    def test_ends_with_what_next(self):
        out = MockLLM().complete("You are the C# Architect.", "Build class")
        assert out.rstrip().endswith("What next?")

    def test_extracts_agent_name(self):
        out = MockLLM().complete("You are the C++ Reviewer. Review.", "review")
        assert "C++ Reviewer" in out

    def test_detects_cpp_only(self):
        out = MockLLM().complete("You are the C++ Orchestrator only.", "task")
        assert "C++" in out and "C#/" not in out

    def test_detects_both_languages(self):
        out = MockLLM().complete("You write C++ and C#.", "task")
        assert "C++/C#" in out


class TestOpenCodeZenLLM:
    def test_default_model(self):
        client = OpenCodeZenLLM("sk-test")
        assert client.model == "deepseek-v4.1-flash-free"

    def test_custom_model(self):
        client = OpenCodeZenLLM("sk-test", model="mimo-7b")
        assert client.model == "mimo-7b"

    def test_network_error_returns_fallback(self):
        client = OpenCodeZenLLM("sk-test", base_url="http://127.0.0.1:1/v1")
        out = client.complete("sys", "msg")
        assert "OpenCode Zen error" in out
        assert "What next?" in out


class TestFactory:
    def test_no_live_flag_returns_mock(self):
        import os
        os.environ.pop("GAMECODE_USE_LIVE_LLM", None)
        client = make_client("sk-test-key-12345")
        assert isinstance(client, MockLLM)

    def test_none_key_returns_mock(self):
        client = make_client(None)
        assert isinstance(client, MockLLM)


class TestGroq:
    def test_groq_defaults(self, monkeypatch):
        from gamecode.llm import GroqLLM
        monkeypatch.delenv("GROQ_MODEL", raising=False)
        c = GroqLLM("gsk_test")
        assert c.base_url == "https://api.groq.com/openai/v1"
        assert c.model == "openai/gpt-oss-20b"

    def test_factory_prefers_groq_when_live(self, monkeypatch):
        from gamecode.llm import GroqLLM
        monkeypatch.setenv("GAMECODE_USE_LIVE_LLM", "1")
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
        assert isinstance(make_client("sk-test-key-1234567890abc"), GroqLLM)

    def test_factory_uses_zen_without_groq_key(self, monkeypatch):
        monkeypatch.setenv("GAMECODE_USE_LIVE_LLM", "1")
        monkeypatch.delenv("GROQ_API_KEY", raising=False)
        assert isinstance(make_client("sk-test-key-1234567890abc"), OpenCodeZenLLM)

    def test_factory_mock_when_not_live(self, monkeypatch):
        monkeypatch.delenv("GAMECODE_USE_LIVE_LLM", raising=False)
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
        assert isinstance(make_client("sk-test-key-1234567890abc"), MockLLM)
    

class TestRouted:
    def test_each_agent_has_its_own_model(self):
        from gamecode.llm import AGENT_MODELS, RoutedLLM
        r = RoutedLLM("gsk_test")
        for name, model in AGENT_MODELS.items():
            assert r._clients[name].model == model
        assert len(set(AGENT_MODELS.values())) >= 2

    def test_set_agent_picks_that_agents_client(self):
        from gamecode.llm import RoutedLLM
        r = RoutedLLM("gsk_test")
        seen = []
        for name, c in r._clients.items():
            c.complete = lambda s, u, n=name: seen.append(n) or "x"
        r.set_agent("Agent2")
        r.complete("sys", "msg")
        assert seen == ["Agent2"]

    def test_live_with_groq_key_gives_router(self, monkeypatch):
        from gamecode.llm import RoutedLLM, make_agent_client
        monkeypatch.setenv("GAMECODE_USE_LIVE_LLM", "1")
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
        assert isinstance(make_agent_client("sk-test-key-1234567890abc"), RoutedLLM)

    def test_not_live_gives_mock(self, monkeypatch):
        from gamecode.llm import make_agent_client
        monkeypatch.delenv("GAMECODE_USE_LIVE_LLM", raising=False)
        assert isinstance(make_agent_client("sk-test-key-1234567890abc"), MockLLM)