"""
security.py — cryptographic primitives, persistent license, encrypted prompt store.

Covers Core Requirements:
  * #2 Robust encryption — prompts encrypted on disk, decrypted only while active,
    cleared from memory on switch.
  * #5 License expiry — 2-day license, encrypted, persisted across restarts.
"""

from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.exceptions import InvalidTag

# ── Tunables ─────────────────────────────────────────────────────────────
LICENSE_DURATION_DAYS = int(os.getenv("GAMECODE_LICENSE_DAYS", "2"))
PBKDF2_ITERATIONS = 200_000
KEY_LEN = 32      # 256-bit AES key
SALT_LEN = 16
NONCE_LEN = 12
MIN_BLOB_LEN = SALT_LEN + NONCE_LEN + 16  # +16 for GCM tag


# ── Errors ───────────────────────────────────────────────────────────────
class DecryptionError(Exception):
    """Raised when an encrypted blob is tampered with or the key is wrong."""


# ── Key derivation ───────────────────────────────────────────────────────
class KeyDerivation:
    """PBKDF2-HMAC-SHA256: turn a user API key into a 256-bit AES key."""

    @staticmethod
    def derive(api_key: str, salt: bytes) -> bytes:
        if not api_key:
            raise ValueError("API key must be non-empty")
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=KEY_LEN,
            salt=salt,
            iterations=PBKDF2_ITERATIONS,
        )
        return kdf.derive(api_key.encode("utf-8"))


# ── AES-256-GCM ──────────────────────────────────────────────────────────
class AES256Cipher:
    """
    Authenticated encryption with AES-256-GCM.

    Wire format:  salt(16) || nonce(12) || ciphertext||tag
    A fresh salt + nonce per encryption — no key or nonce reuse across blobs.
    """

    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("API key must be non-empty")
        self._api_key = api_key

    def encrypt(self, plaintext: str) -> bytes:
        salt = secrets.token_bytes(SALT_LEN)
        nonce = secrets.token_bytes(NONCE_LEN)
        key = KeyDerivation.derive(self._api_key, salt)
        ct = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
        return salt + nonce + ct

    def decrypt(self, blob: bytes) -> str:
        if len(blob) < MIN_BLOB_LEN:
            raise DecryptionError("Encrypted payload too short / corrupted.")
        salt = blob[:SALT_LEN]
        nonce = blob[SALT_LEN:SALT_LEN + NONCE_LEN]
        ct = blob[SALT_LEN + NONCE_LEN:]
        key = KeyDerivation.derive(self._api_key, salt)
        try:
            return AESGCM(key).decrypt(nonce, ct, None).decode("utf-8")
        except InvalidTag as e:
            raise DecryptionError("Authentication failed — wrong key or tampered data.") from e


# ── Persistent license ───────────────────────────────────────────────────
class LicenseManager:
    """
    Encrypted, persistent license file.

    File:  <license_dir>/license.lic
    Blob:  AES-256-GCM(JSON{install_date, expiry_date, license_id})
    """

    def __init__(self, api_key: str, license_dir: Path | str):
        self._cipher = AES256Cipher(api_key)
        self._path = Path(license_dir) / "license.lic"
        self._path.parent.mkdir(parents=True, exist_ok=True)

    # Internal ------------------------------------------------------------
    def _load(self) -> Optional[dict]:
        if not self._path.exists():
            return None
        try:
            return json.loads(self._cipher.decrypt(self._path.read_bytes()))
        except (DecryptionError, json.JSONDecodeError):
            return None  # corrupt / wrong-key → treated as "no license"

    def _save(self, data: dict) -> None:
        self._path.write_bytes(self._cipher.encrypt(json.dumps(data)))

    # Public --------------------------------------------------------------
    def initialize_or_load(self) -> dict:
        data = self._load()
        if data is None:
            now = datetime.now(timezone.utc)
            data = {
                "install_date": now.isoformat(),
                "expiry_date": (now + timedelta(days=LICENSE_DURATION_DAYS)).isoformat(),
                "license_id": secrets.token_hex(8),
            }
            self._save(data)
        return data

    def status(self) -> dict:
        data = self.initialize_or_load()
        expiry = datetime.fromisoformat(data["expiry_date"])
        now = datetime.now(timezone.utc)
        remaining = expiry - now
        return {
            "valid": now < expiry,
            "install_date": data["install_date"],
            "expiry_date": data["expiry_date"],
            "license_id": data["license_id"],
            "days_remaining": max(0, remaining.days),
            "seconds_remaining": max(0, int(remaining.total_seconds())),
        }

    def is_valid(self) -> bool:
        return self.status()["valid"]


# ── Encrypted prompt store ───────────────────────────────────────────────
class PromptStore:
    """
    Encrypted on-disk prompt storage with strict in-memory discipline.

    Invariants:
      * Prompts exist on disk ONLY as AES-256-GCM blobs.
      * Exactly one prompt is decrypted in memory at any moment (the active agent's).
      * Switching agents clears the previous prompt BEFORE loading the next.
    """

    def __init__(self, api_key: str, prompts_dir: Path | str):
        self._cipher = AES256Cipher(api_key)
        self._dir = Path(prompts_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._active_prompt: Optional[str] = None
        self._active_agent: Optional[str] = None

    def save_prompt(self, agent_name: str, prompt: str) -> Path:
        path = self._dir / f"{agent_name}.enc"
        path.write_bytes(self._cipher.encrypt(prompt))
        return path

    def load_prompt(self, agent_name: str) -> str:
        path = self._dir / f"{agent_name}.enc"
        if not path.exists():
            raise FileNotFoundError(f"No encrypted prompt for '{agent_name}'")
        # Clear BEFORE decrypt so a decrypt failure doesn't leave stale text.
        self.clear_active()
        self._active_prompt = self._cipher.decrypt(path.read_bytes())
        self._active_agent = agent_name
        return self._active_prompt

    def get_active_prompt(self) -> Optional[str]:
        return self._active_prompt

    def get_active_agent(self) -> Optional[str]:
        return self._active_agent

    def clear_active(self) -> None:
        self._active_prompt = None
        self._active_agent = None