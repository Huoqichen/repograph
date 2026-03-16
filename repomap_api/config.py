from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class Settings:
    cors_origins: list[str]
    clone_dir: str | None
    cache_dir: str
    cache_ttl_seconds: int


def get_settings() -> Settings:
    origins_raw = os.getenv("REPOMAP_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
    origins = [origin.strip() for origin in origins_raw.split(",") if origin.strip()]
    clone_dir = os.getenv("REPOMAP_CLONE_DIR")
    default_cache_dir = Path(__file__).resolve().parents[1] / ".codex-temp-cache" / "analysis-cache"
    cache_dir = os.getenv("REPOMAP_CACHE_DIR", str(default_cache_dir))
    cache_ttl_seconds = int(os.getenv("REPOMAP_CACHE_TTL_SECONDS", "86400"))
    return Settings(
        cors_origins=origins,
        clone_dir=clone_dir,
        cache_dir=cache_dir,
        cache_ttl_seconds=cache_ttl_seconds,
    )
