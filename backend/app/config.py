"""Configuration centralisée (variables d'environnement préfixées CH_, fichier .env optionnel)."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CH_", env_file=ROOT / ".env", extra="ignore")

    data_dir: Path = ROOT / "data"
    host: str = "127.0.0.1"
    port: int = 8765
    localhost_trusted: bool = True
    log_level: str = "INFO"
    user_agent: str = "ConcoursHunter/0.1 (+usage personnel; respecte robots.txt)"
    http_timeout: float = 20.0
    min_delay_per_domain_s: float = 5.0
    max_backups: int = 10
    scheduler_enabled: bool = True
    seed_sources: bool = True

    @property
    def db_path(self) -> Path:
        return self.data_dir / "concours.db"

    @property
    def proofs_dir(self) -> Path:
        return self.data_dir / "proofs"

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    def ensure_dirs(self) -> None:
        for p in (self.data_dir, self.proofs_dir, self.backups_dir, self.cache_dir):
            p.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s


def reset_settings_cache() -> None:
    get_settings.cache_clear()
