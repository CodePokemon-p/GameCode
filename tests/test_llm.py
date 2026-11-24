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
        assert client.model == "deepseek-chat"

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