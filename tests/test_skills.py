"""Tests for the skills loader."""
from pathlib import Path

from gamecode.skills import load_skills


def _write(root: Path, folder: str, text: str) -> None:
    d = root / folder
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(text, encoding="utf-8")


def test_missing_folder_returns_empty(tmp_path):
    assert load_skills(tmp_path / "nope") == []


def test_reads_name_and_description(tmp_path):
    _write(tmp_path, "demo", "---\nname: demo-skill\ndescription: Does a thing\n---\n# Body\n")
    skills = load_skills(tmp_path)
    assert len(skills) == 1
    assert skills[0].name == "demo-skill"
    assert skills[0].description == "Does a thing"


def test_falls_back_to_folder_name_without_frontmatter(tmp_path):
    _write(tmp_path, "plain", "# Just text, no frontmatter\n")
    skills = load_skills(tmp_path)
    assert skills[0].name == "plain"
    assert skills[0].description == ""


def test_real_project_skill_loads():
    skills_dir = Path(__file__).resolve().parent.parent / "skills"
    names = [s.name for s in load_skills(skills_dir)]
    assert "mcp-builder" in names