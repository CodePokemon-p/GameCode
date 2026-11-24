"""Shared pytest fixtures."""
from pathlib import Path

import pytest

from gamecode.agents import AgentManager
from gamecode.security import AES256Cipher, LicenseManager, PromptStore


@pytest.fixture
def api_key() -> str:
    return "sk-test-key-12345"


@pytest.fixture
def cipher(api_key: str) -> AES256Cipher:
    return AES256Cipher(api_key)


@pytest.fixture
def license_mgr(api_key: str, tmp_path: Path) -> LicenseManager:
    return LicenseManager(api_key, tmp_path / "licenses")


@pytest.fixture
def prompt_store(api_key: str, tmp_path: Path) -> PromptStore:
    return PromptStore(api_key, tmp_path / "prompts")


@pytest.fixture
def agent_mgr(api_key: str, tmp_path: Path) -> AgentManager:
    mgr = AgentManager(
        api_key,
        prompts_dir=tmp_path / "prompts",
        license_dir=tmp_path / "licenses",
    )
    mgr.activate_initial()
    return mgr