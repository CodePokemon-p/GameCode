"""Tests for AES-256-GCM cipher, license, and prompt store."""
import json
from datetime import datetime, timedelta, timezone

import pytest

from gamecode.security import (
    AES256Cipher,
    DecryptionError,
    LicenseManager,
    PromptStore,
)


# ── AES256Cipher ────────────────────────────────────────────────────────
class TestAES256Cipher:
    def test_roundtrip(self, cipher):
        plain = "You are the C++ Orchestrator."
        assert cipher.decrypt(cipher.encrypt(plain)) == plain

    def test_plaintext_not_in_ciphertext(self, cipher):
        blob = cipher.encrypt("Orchestrator secret prompt")
        assert b"Orchestrator" not in blob
        assert b"secret" not in blob

    def test_same_plaintext_different_ciphertext(self, cipher):
        """Fresh salt + nonce every call — no deterministic output."""
        assert cipher.encrypt("hello") != cipher.encrypt("hello")

    def test_wrong_key_raises(self, cipher):
        blob = cipher.encrypt("secret")
        with pytest.raises(DecryptionError):
            AES256Cipher("different-key").decrypt(blob)

    def test_tampered_ciphertext_raises(self, cipher):
        blob = bytearray(cipher.encrypt("hello world"))
        blob[-1] ^= 0xFF
        with pytest.raises(DecryptionError):
            cipher.decrypt(bytes(blob))

    def test_truncated_blob_raises(self, cipher):
        with pytest.raises(DecryptionError):
            cipher.decrypt(b"\x00" * 10)

    def test_empty_api_key_rejected(self):
        with pytest.raises(ValueError):
            AES256Cipher("")


# ── LicenseManager ──────────────────────────────────────────────────────
class TestLicenseManager:
    def test_initializes_valid(self, license_mgr):
        assert license_mgr.is_valid() is True

    def test_persists_across_instances(self, api_key, tmp_path):
        first = LicenseManager(api_key, tmp_path / "licenses").initialize_or_load()
        second = LicenseManager(api_key, tmp_path / "licenses").initialize_or_load()
        assert first["license_id"] == second["license_id"]
        assert first["install_date"] == second["install_date"]

    def test_default_two_days(self, license_mgr):
        status = license_mgr.status()
        assert status["days_remaining"] in (1, 2)

    def test_expired_license_detected(self, license_mgr):
        data = license_mgr.initialize_or_load()
        data["expiry_date"] = (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).isoformat()
        license_mgr._save(data)
        assert license_mgr.is_valid() is False

    def test_corrupt_file_treated_as_fresh(self, api_key, tmp_path):
        lic_dir = tmp_path / "licenses"
        lic_dir.mkdir()
        (lic_dir / "license.lic").write_bytes(b"garbage not a valid blob")
        mgr = LicenseManager(api_key, lic_dir)
        fresh = mgr.initialize_or_load()
        assert "license_id" in fresh
        assert mgr.is_valid() is True

    def test_wrong_key_generates_new_license(self, api_key, tmp_path):
        dir_path = tmp_path / "licenses"
        first = LicenseManager(api_key, dir_path).initialize_or_load()
        second = LicenseManager("different-key", dir_path).initialize_or_load()
        assert first["license_id"] != second["license_id"]


# ── PromptStore ─────────────────────────────────────────────────────────
class TestPromptStore:
    def test_save_encrypts_on_disk(self, prompt_store, tmp_path):
        prompt_store.save_prompt("Agent1", "Orchestrator prompt")
        blob = (tmp_path / "prompts" / "Agent1.enc").read_bytes()
        assert b"Orchestrator" not in blob

    def test_load_returns_plaintext(self, prompt_store):
        prompt_store.save_prompt("Agent1", "Orchestrator prompt")
        assert prompt_store.load_prompt("Agent1") == "Orchestrator prompt"

    def test_switch_clears_previous_prompt(self, prompt_store):
        prompt_store.save_prompt("Agent1", "C++ prompt")
        prompt_store.save_prompt("Agent2", "C# prompt")
        prompt_store.load_prompt("Agent1")
        assert prompt_store.get_active_agent() == "Agent1"
        prompt_store.load_prompt("Agent2")
        assert prompt_store.get_active_prompt() == "C# prompt"
        assert prompt_store.get_active_agent() == "Agent2"

    def test_load_missing_raises(self, prompt_store):
        with pytest.raises(FileNotFoundError):
            prompt_store.load_prompt("DoesNotExist")

    def test_corrupt_blob_clears_memory_before_raising(
        self, prompt_store, tmp_path
    ):
        """Fail-closed: old prompt must be gone even if new decrypt fails."""
        prompt_store.save_prompt("Agent1", "C++ prompt")
        prompt_store.load_prompt("Agent1")
        assert prompt_store.get_active_prompt() == "C++ prompt"

        (tmp_path / "prompts" / "Agent2.enc").write_bytes(b"\x00" * 50)
        with pytest.raises(DecryptionError):
            prompt_store.load_prompt("Agent2")
        assert prompt_store.get_active_prompt() is None
        assert prompt_store.get_active_agent() is None