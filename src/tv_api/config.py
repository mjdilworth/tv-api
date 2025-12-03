"""Application configuration helpers."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ASSETS_DIR = PROJECT_ROOT / "assets"


class Settings(BaseSettings):
    """Runtime configuration read from environment variables."""

    app_name: str = Field(default="PickleTV API")
    environment: str = Field(default="local")
    log_level: str = Field(default="INFO")
    assets_dir: Path = Field(default=DEFAULT_ASSETS_DIR)

    model_config = SettingsConfigDict(env_prefix="TV_API_", case_sensitive=False)


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings object so expensive IO only runs once."""

    return Settings()
