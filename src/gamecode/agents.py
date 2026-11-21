"""
agents.py — 5-agent pipeline, subagents, guardrails, agent manager.

Covers Core Requirements:
  * #1 5-agent architecture (5 primaries, each with a subagent)
  * #3 Comprehensive guardrails (injection, off-topic, language,
       plan-type no-edit, mandatory "What next?")
  * #4 context hand-off is wired in Phase 2 (TUI); this module exposes
       the hooks the hand-off layer needs.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .security import LicenseManager, PromptStore


# ── Roles & registry ────────────────────────────────────────────────────
class AgentRole(str, Enum):
    CPP_ORCHESTRATOR = "Agent1"
    CSHARP_ARCHITECT = "Agent2"
    CPP_REVIEWER     = "Agent3"
    CSHARP_DEBUGGER  = "Agent4"
    SYSTEMS_ENGINEER = "Agent5"


AGENT_ORDER: list[AgentRole] = [
    AgentRole.CPP_ORCHESTRATOR,
    AgentRole.CSHARP_ARCHITECT,
    AgentRole.CPP_REVIEWER,
    AgentRole.CSHARP_DEBUGGER,
    AgentRole.SYSTEMS_ENGINEER,
]


# ── Agent definitions ───────────────────────────────────────────────────
@dataclass(frozen=True)
class AgentSpec:
    role: AgentRole
    display_name: str
    prompt: str
    can_edit_files: bool            # plan-type agents set this False
    subagent_name: str
    subagent_prompt: str


AGENT_SPECS: dict[AgentRole, AgentSpec] = {
    AgentRole.CPP_ORCHESTRATOR: AgentSpec(
        role=AgentRole.CPP_ORCHESTRATOR,
        display_name="C++ Orchestrator",
        can_edit_files=False,       # plan-type
        prompt=(
            "You are the C++ Orchestrator. Your job is to plan C++ work, "
            "break tasks into steps, and coordinate. You do NOT edit files "
            "or run builds — you produce plans only. "
            "Refuse off-topic queries (weather, politics, general knowledge). "
            "Refuse any language other than C++ or C#. "
            "Always finish your reply with the exact line: 'What next?'."
        ),
        subagent_name="Agent1a",
        subagent_prompt=(
            "You are the C++ Snippet Helper, subagent to Agent1. "
            "You produce small, self-contained C++ snippets when asked. "
            "Never write Python/JS/Rust/Java. Always end with 'What next?'."
        ),
    ),
    AgentRole.CSHARP_ARCHITECT: AgentSpec(
        role=AgentRole.CSHARP_ARCHITECT,
        display_name="C# Architect",
        can_edit_files=True,        # build-type
        prompt=(
            "You are the C# Architect. You design and write C# code. "
            "Refuse off-topic queries. Refuse any language other than C# or C++. "
            "Always finish your reply with the exact line: 'What next?'."
        ),
        subagent_name="Agent2a",
        subagent_prompt=(
            "You are the C# Pattern Advisor, subagent to Agent2. "
            "You propose idiomatic C# design patterns. "
            "Refuse off-topic. Refuse non-C#/C++ languages. End with 'What next?'."
        ),
    ),
    AgentRole.CPP_REVIEWER: AgentSpec(
        role=AgentRole.CPP_REVIEWER,
        display_name="C++ Reviewer",
        can_edit_files=False,       # plan-type — review only
        prompt=(
            "You are the C++ Reviewer. You read and critique C++ code. "
            "You do NOT edit files or run builds. "
            "Refuse off-topic queries. Refuse non-C++/C# languages. "
            "Always finish your reply with the exact line: 'What next?'."
        ),
        subagent_name="Agent3a",
        subagent_prompt=(
            "You are the C++ Static Analysis Helper, subagent to Agent3. "
            "You reason about undefined behaviour, ownership, and RAII. "
            "End with 'What next?'."
        ),
    ),
    AgentRole.CSHARP_DEBUGGER: AgentSpec(
        role=AgentRole.CSHARP_DEBUGGER,
        display_name="C# Debugger",
        can_edit_files=True,        # build-type — debugger patches code
        prompt=(
            "You are the C# Debugger. You diagnose and patch C# code. "
            "Refuse off-topic queries. Refuse non-C#/C++ languages. "
            "Always finish your reply with the exact line: 'What next?'."
        ),
        subagent_name="Agent4a",
        subagent_prompt=(
            "You are the C# Stack Tracer, subagent to Agent4. "
            "You read exception traces and identify root cause. "
            "End with 'What next?'."
        ),
    ),
    AgentRole.SYSTEMS_ENGINEER: AgentSpec(
        role=AgentRole.SYSTEMS_ENGINEER,
        display_name="Systems Engineer",
        can_edit_files=True,        # build-type
        prompt=(
            "You are the Systems Engineer. You write C++ and C# and glue "
            "components together. Refuse off-topic queries. Refuse all "
            "other languages. Always finish your reply with the exact line: "
            "'What next?'."
        ),
        subagent_name="Agent5a",
        subagent_prompt=(
            "You are the Cross-language Glue Helper, subagent to Agent5. "
            "You design C++/C# interop (P/Invoke, C++/CLI). "
            "End with 'What next?'."
        ),
    ),
}


# ── Guardrails ──────────────────────────────────────────────────────────
@dataclass
class GuardrailResult:
    allowed: bool
    reason: str = ""


class Guardrail:
    """
    Five-check input safety gate:

      1. size sanity          (non-empty, ≤ MAX_INPUT_LEN)
      2. prompt-injection     (keyword patterns)
      3. off-topic            (weather / politics / general knowledge)
      4. language restriction (only C++ / C# permitted)
      5. plan-type edit block (plan agents may not edit files / run builds)
    """

    MAX_INPUT_LEN = 4000

    INJECTION_PATTERNS = [
        "ignore previous", "ignore all previous", "ignore the above",
        "disregard previous", "disregard the above", "disregard all",
        "forget your instructions", "forget your prompt",
        "reveal your prompt", "reveal the prompt", "show your prompt",
        "print your prompt", "print your instructions",
        "system prompt", "system message",
        "you are now", "jailbreak", "developer mode",
        "<|system|>", "<|im_start|>", "### system:",
    ]

    OFF_TOPIC_KEYWORDS = [
        "weather", "forecast", "president", "politics", "election",
        "religion", "god", "joke", "recipe", "sing", "song",
        "who are you", "what is your name", "who made you",
        "who created you", "tell me a story",
    ]

    # Exact word match — "java" must NOT match "javascript" (regex \b handles it).
    BLOCKED_LANGUAGES = [
        "python", "javascript", "typescript", "rust", "java",
        "ruby", "golang", "go lang", "kotlin", "swift", "php",
        "perl", "scala", "haskell", "elixir", "clojure",
        "nodejs", "node.js",
    ]

    PLAN_TYPE_BLOCKED_VERBS = [
        "write file", "write to file", "create file", "create a file",
        "save to", "save the file", "delete file", "delete the file",
        "edit the file", "edit this file", "modify the file",
        "modify this file", "patch the file", "apply this patch",
        "mkdir", "rmdir", "touch ",
        "run build", "run the build", "dotnet build", "g++ ", "clang++ ",
        "compile and run", "make install",
    ]

    @classmethod
    def check(cls, user_input: str, *, can_edit_files: bool) -> GuardrailResult:
        text = (user_input or "").strip()
        if not text:
            return GuardrailResult(False, "Empty input.")
        if len(text) > cls.MAX_INPUT_LEN:
            return GuardrailResult(
                False, f"🚫 Input exceeds {cls.MAX_INPUT_LEN} characters."
            )

        lower = text.lower()

        for pat in cls.INJECTION_PATTERNS:
            if pat in lower:
                return GuardrailResult(
                    False,
                    "🚫 GUARDRAIL: Prompt-injection pattern detected. "
                    "Submit a normal coding request.",
                )

        for kw in cls.OFF_TOPIC_KEYWORDS:
            if re.search(rf"\b{re.escape(kw)}\b", lower):
                return GuardrailResult(
                    False,
                    "🚫 GUARDRAIL: Off-topic query. "
                    "I only assist with C++ and C# development.",
                )

        for lang in cls.BLOCKED_LANGUAGES:
            if re.search(rf"\b{re.escape(lang)}\b", lower):
                return GuardrailResult(
                    False,
                    f"🚫 GUARDRAIL: Language restricted. I only write C++ and C# "
                    f"(blocked: {lang}).",
                )

        if not can_edit_files:
            for verb in cls.PLAN_TYPE_BLOCKED_VERBS:
                if verb in lower:
                    return GuardrailResult(
                        False,
                        "🚫 GUARDRAIL: This is a plan-type agent — it may not "
                        "edit files or run builds. Press Tab to switch to a "
                        "build-type agent (Agent2, Agent4, or Agent5).",
                    )

        return GuardrailResult(True)


# ── Agent manager ───────────────────────────────────────────────────────
@dataclass
class AgentResponse:
    allowed: bool
    agent: str
    display_name: str
    response: str
    is_plan_type: bool


WHAT_NEXT_LINE = "What next?"


class AgentManager:
    """Owns the 5-agent pipeline, encrypted prompts, license, and dispatch."""

    def __init__(
        self,
        api_key: str,
        prompts_dir: Path | str,
        license_dir: Path | str,
    ):
        self.prompt_store = PromptStore(api_key, prompts_dir)
        self.license = LicenseManager(api_key, license_dir)
        self._index: int = 0

    # Lifecycle -----------------------------------------------------------
    def bootstrap_prompts(self) -> None:
        """Write encrypted prompts for any agent/subagent missing on disk."""
        for spec in AGENT_SPECS.values():
            for name, prompt in (
                (spec.role.value, spec.prompt),
                (spec.subagent_name, spec.subagent_prompt),
            ):
                path = self.prompt_store._dir / f"{name}.enc"
                if not path.exists():
                    self.prompt_store.save_prompt(name, prompt)

    def activate_initial(self) -> AgentRole:
        self.bootstrap_prompts()
        self.prompt_store.load_prompt(self.current_agent.value)
        return self.current_agent

    # State ---------------------------------------------------------------
    @property
    def current_agent(self) -> AgentRole:
        return AGENT_ORDER[self._index]

    @property
    def current_spec(self) -> AgentSpec:
        return AGENT_SPECS[self.current_agent]

    def get_subagents(self, role: AgentRole) -> list[str]:
        return [AGENT_SPECS[role].subagent_name]

    # Switching -----------------------------------------------------------
    def switch_to_next(self) -> AgentRole:
        """Tab action. Clears old prompt, advances, loads new prompt."""
        self._index = (self._index + 1) % len(AGENT_ORDER)
        self.prompt_store.load_prompt(self.current_agent.value)
        return self.current_agent

    # Dispatch ------------------------------------------------------------
    def process(self, user_input: str) -> AgentResponse:
        spec = self.current_spec

        if not self.license.is_valid():
            return AgentResponse(
                allowed=False,
                agent=spec.role.value,
                display_name=spec.display_name,
                response="⛔ LICENSE EXPIRED. All agents and tools are locked.",
                is_plan_type=not spec.can_edit_files,
            )

        guard = Guardrail.check(user_input, can_edit_files=spec.can_edit_files)
        if not guard.allowed:
            return AgentResponse(
                allowed=False,
                agent=spec.role.value,
                display_name=spec.display_name,
                response=guard.reason,
                is_plan_type=not spec.can_edit_files,
            )

        # TODO Phase 3: replace stub with OpenCode Zen call.
        body = (
            f"[{spec.display_name}] Processing: '{user_input}'. "
            f"(LLM not wired up yet — Phase 3.)"
        )
        if WHAT_NEXT_LINE.lower() not in body.lower():
            body = body.rstrip() + "\n\n" + WHAT_NEXT_LINE

        return AgentResponse(
            allowed=True,
            agent=spec.role.value,
            display_name=spec.display_name,
            response=body,
            is_plan_type=not spec.can_edit_files,
        )