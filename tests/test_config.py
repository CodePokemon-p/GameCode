"""Tests for API key config persistence."""
from pathlib import Path

import pytest

from gamecode.config import Config


@pytest.fixture
def cfg(tmp_path: Path) -> Config:
    return Config(tmp_path / "cfg")


class TestConfigPersistence:
    def test_load_when_missing_returns_none(self, cfg):
        assert cfg.load_api_key() is None

    def test_save_and_load_roundtrip(self, cfg):
        cfg.save_api_key("sk-test-key-1234567890")
        assert cfg.load_api_key() == "sk-test-key-1234567890"

    def test_clear_removes_key(self, cfg):
        cfg.save_api_key("sk-test-key-1234567890")
        cfg.clear_api_key()
        assert cfg.load_api_key() is None

    def test_corrupt_json_returns_none(self, cfg):
        cfg.config_path.write_text("not json")
        assert cfg.load_api_key() is None


class TestFormatValidation:
    @pytest.mark.parametrize("key", [
        "sk-test-key-1234567890",
        "sk-" + "a" * 20,
    ])
    def test_valid_keys(self, key):
        assert Config.validate_format(key) is True

    @pytest.mark.parametrize("key", [
        "", "sk-short", "not-a-key-12345678901234", None,
        "pk-test-key-12345678901234",
    ])
    def test_invalid_keys(self, key):
        assert Config.validate_format(key) is False