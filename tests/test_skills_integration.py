"""Skills are listed in the system prompt sent to the LLM."""
from gamecode.agents import AgentManager
from gamecode.llm import LLMClient

KEY = "sk-test-key-1234567890abc"


class Spy(LLMClient):
    def __init__(self):
        self.seen = ""

    def complete(self, system_prompt, user_message):
        self.seen = system_prompt
        return "ok"


def _mgr(tmp_path, skills_dir, spy):
    return AgentManager(
        KEY, tmp_path / "p", tmp_path / "l",
        llm_client=spy, skills_dir=skills_dir,
    )


def test_skills_listed_in_prompt(tmp_path):
    d = tmp_path / "skills" / "demo"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        "---\nname: demo-skill\ndescription: Does a thing\n---\n", encoding="utf-8"
    )
    spy = Spy()
    _mgr(tmp_path, tmp_path / "skills", spy).process("Plan a C++ linked list")
    assert "demo-skill" in spy.seen
    assert "reference only" in spy.seen


def test_no_skills_dir_leaves_prompt_alone(tmp_path):
    spy = Spy()
    _mgr(tmp_path, None, spy).process("Plan a C++ linked list")
    assert "Available skills" not in spy.seen