"""llm.py — LLM abstraction. Mock for demo, OpenCodeZen for live."""
from __future__ import annotations

import json
import os
import urllib.request
from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    def complete(self, system_prompt: str, user_message: str) -> str: ...


class MockLLM(LLMClient):
    """Deterministic response for test-task demo. No network required."""

    def complete(self, system_prompt: str, user_message: str) -> str:
        agent = self._extract_agent_name(system_prompt)
        lang = self._detect_language(system_prompt)
        return (
            f"As **{agent}**, here's my plan for: *{user_message}*\n\n"
            f"**Language scope:** {lang}\n\n"
            f"1. Break the problem into components\n"
            f"2. Design the {lang} structure\n"
            f"3. Implement with best practices\n"
            f"4. Review for correctness\n\n"
            f"_(Mock LLM — configure OPENCODE_ZEN_API_KEY to switch to live responses.)_\n\n"
            f"What next?"
        )

    @staticmethod
    def _extract_agent_name(prompt: str) -> str:
        for line in prompt.split("\n"):
            if "You are the" in line:
                return line.split("You are the", 1)[1].split(".")[0].strip()
        return "agent"

    @staticmethod
    def _detect_language(prompt: str) -> str:
        has_cpp = "C++" in prompt
        has_cs = "C#" in prompt
        if has_cpp and not has_cs:
            return "C++"
        if has_cs and not has_cpp:
            return "C#"
        return "C++/C#"


class OpenCodeZenLLM(LLMClient):
    """Live client. Requires a valid OpenCode Zen API key."""

    label = "OpenCode Zen"

    def __init__(
        self,
        api_key: str,
        base_url: str | None = None,
        model: str | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url or os.getenv(
            "OPENCODE_ZEN_BASE_URL", "https://opencode.ai/zen/v1"
        )
        self.model = model or os.getenv(
            "OPENCODE_ZEN_MODEL", "deepseek-v4.1-flash-free"
        )

    def complete(self, system_prompt: str, user_message: str) -> str:
        payload = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": 0.7,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "User-Agent": "GameCode/0.1",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read())
                text = data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            return (
            f"[{self.label} error: {e}. Falling back to local response.]\n\n"
                f"What next?"
            )

        if "what next" not in text.lower():
            text = text.rstrip() + "\n\nWhat next?"
        return text


class GroqLLM(OpenCodeZenLLM):
    """Outside-provider client (Groq). Same OpenAI-style API as Zen."""

    label = "LLM"

    def __init__(self, api_key: str, model: str | None = None):
        super().__init__(
            api_key,
            base_url="https://api.groq.com/openai/v1",
            model=model or os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
        )


class GroqLLM(OpenCodeZenLLM):
    """Outside-provider client (Groq). Same OpenAI-style API as Zen."""

    label = "LLM"

    def __init__(self, api_key: str, model: str | None = None):
        super().__init__(
            api_key,
            base_url="https://api.groq.com/openai/v1",
            model=model or os.getenv("GROQ_MODEL", "openai/gpt-oss-20b"),
        )


def make_client(api_key: str | None) -> LLMClient:
    """Mock unless GAMECODE_USE_LIVE_LLM=1; then Groq if GROQ_API_KEY, else Zen."""
    if os.getenv("GAMECODE_USE_LIVE_LLM") != "1":
        return MockLLM()
    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        return GroqLLM(groq_key)
    if api_key:
        return OpenCodeZenLLM(api_key)
    return MockLLM()


AGENT_MODELS = {
    "Agent1": "openai/gpt-oss-120b",
    "Agent2": "qwen/qwen3.8-27b",
    "Agent3": "openai/gpt-oss-20b",
    "Agent4": "qwen/qwen3.8-27b",
    "Agent5": "openai/gpt-oss-120b",
}


class RoutedLLM(LLMClient):
    """Gives each agent its own default model."""

    def __init__(self, groq_key: str, models: dict[str, str] | None = None):
        self.models = dict(models or AGENT_MODELS)
        self._clients = {
            name: GroqLLM(groq_key, model=model)
            for name, model in self.models.items()
        }
        self._current: str | None = None

    def set_agent(self, name: str) -> None:
        self._current = name

    def complete(self, system_prompt: str, user_message: str) -> str:
        client = self._clients.get(self._current) or next(iter(self._clients.values()))
        return client.complete(system_prompt, user_message)


def make_agent_client(api_key: str | None) -> LLMClient:
    """Per-agent models when live with a Groq key; otherwise same as make_client."""
    if os.getenv("GAMECODE_USE_LIVE_LLM") == "1" and os.getenv("GROQ_API_KEY"):
        return RoutedLLM(os.environ["GROQ_API_KEY"])
    return make_client(api_key)