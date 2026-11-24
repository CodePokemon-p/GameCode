"""config.py — API key persistence in %APPDATA%\\GameCode\\config.json."""
from __future__ import annotations

import json
import os
from pathlib import Path


class Config:
    MIN_KEY_LEN = 20
    KEY_PREFIX = "sk-"
    KEY_PREFIXES = ("sk-", "oc_sk_")

    def __init__(self, config_dir: Path | str | None = None):
        if config_dir is None:
            appdata = os.environ.get("APPDATA") or str(Path.home() / ".gamecode")
            config_dir = Path(appdata) / "GameCode"
        self.config_dir = Path(config_dir)
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.config_dir / "config.json"

    def load_api_key(self) -> str | None:
        if not self.config_path.exists():
            return None
        try:
            return json.loads(self.config_path.read_text(encoding="utf-8")).get("api_key")
        except Exception:
            return None

    def save_api_key(self, key: str) -> None:
        self.config_path.write_text(
            json.dumps({"api_key": key}, indent=2), encoding="utf-8"
        )

    def clear_api_key(self) -> None:
        if self.config_path.exists():
            self.config_path.unlink()

    @classmethod
    def validate_format(cls, key: str) -> bool:
                return bool(key) and len(key) >= cls.MIN_KEY_LEN and key.startswith(cls.KEY_PREFIXES)