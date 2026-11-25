"""Agents can call MCP tools; plan-type agents only get read-only ones."""
from gamecode.agents import AgentManager
from gamecode.llm import LLMClient

KEY = "sk-test-key-1234567890abc"
TOOLS = [
    {"name": "list_outputs", "description": "List files."},
    {"name": "read_output", "description": "Read a file."},
    {"name": "write_markdown", "description": "Write a file."},
]
WRITE = 'TOOL: {"tool": "write_markdown", "args": {"name": "a.md", "content": "hi"}}'
LIST = 'TOOL: {"tool": "list_outputs", "args": {}}'


class Scripted(LLMClient):
    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []
        self.messages = []

    def complete(self, system_prompt, user_message):
        self.prompts.append(system_prompt)
        self.messages.append(user_message)
        return self.replies.pop(0) if self.replies else "done"


class FakeMcp:
    def __init__(self):
        self.calls = []

    def list_tools(self):
        return TOOLS

    def call_tool(self, name, arguments=None):
        self.calls.append((name, arguments))
        return f"ran {name}", False


class BrokenMcp:
    def list_tools(self):
        raise RuntimeError("server down")

    def call_tool(self, name, arguments=None):
        raise RuntimeError("server down")


def _mgr(tmp_path, llm, mcp, switches=0):
    m = AgentManager(KEY, tmp_path / "p", tmp_path / "l", llm_client=llm, mcp=mcp)
    m.activate_initial()
    for _ in range(switches):
        m.switch_to_next()
    return m


def test_build_agent_can_write(tmp_path):
    llm, mcp = Scripted([WRITE, "Saved it."]), FakeMcp()
    r = _mgr(tmp_path, llm, mcp, switches=4).process("Write a C++ linked list")
    assert mcp.calls == [("write_markdown", {"name": "a.md", "content": "hi"})]
    assert "Saved it." in r.response
    assert r.response.rstrip().endswith("What next?")
    assert "ran write_markdown" in llm.messages[1]


def test_plan_agent_cannot_write(tmp_path):
    llm, mcp = Scripted([WRITE, "Cannot do that."]), FakeMcp()
    _mgr(tmp_path, llm, mcp).process("Plan a C++ linked list")
    assert mcp.calls == []
    assert "not available" in llm.messages[1]


def test_plan_agent_can_read(tmp_path):
    llm, mcp = Scripted([LIST, "ok"]), FakeMcp()
    _mgr(tmp_path, llm, mcp).process("Plan a C++ linked list")
    assert mcp.calls == [("list_outputs", {})]


def test_prompt_lists_only_allowed_tools(tmp_path):
    plan_llm = Scripted(["ok"])
    _mgr(tmp_path / "a", plan_llm, FakeMcp()).process("Plan a C++ linked list")
    assert "list_outputs" in plan_llm.prompts[0]
    assert "write_markdown" not in plan_llm.prompts[0]

    build_llm = Scripted(["ok"])
    _mgr(tmp_path / "b", build_llm, FakeMcp(), switches=4).process("Write a C++ linked list")
    assert "write_markdown" in build_llm.prompts[0]


def test_no_mcp_means_no_tools_note(tmp_path):
    llm = Scripted(["ok"])
    _mgr(tmp_path, llm, None).process("Plan a C++ linked list")
    assert "Tools you may use" not in llm.prompts[0]


def test_broken_mcp_does_not_break_the_agent(tmp_path):
    llm = Scripted(["Here is the plan."])
    r = _mgr(tmp_path, llm, BrokenMcp()).process("Plan a C++ linked list")
    assert "Here is the plan." in r.response
    assert "Tools you may use" not in llm.prompts[0]