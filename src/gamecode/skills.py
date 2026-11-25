"""skills.py - discovers SKILL.md files in a skills folder."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    path: Path


def _parse_frontmatter(text: str) -> dict[str, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    meta: dict[str, str] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" in line and not line.startswith((" ", "\t")):
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta


def load_skills(skills_dir: Path | str) -> list[Skill]:
    root = Path(skills_dir)
    if not root.is_dir():
        return []
    skills: list[Skill] = []
    for skill_md in sorted(root.glob("*/SKILL.md")):
        try:
            text = skill_md.read_text(encoding="utf-8")
        except OSError:
            continue
        meta = _parse_frontmatter(text)
        skills.append(
            Skill(
                name=meta.get("name") or skill_md.parent.name,
                description=meta.get("description", ""),
                path=skill_md,
            )
        )
    return skills