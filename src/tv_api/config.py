"""Application configuration helpers."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ASSETS_DIR = PROJECT_ROOT / "assets"


class Settings(BaseSettings):
    """Runtime configuration read from environment variables."""

    app_name: str = Field(default="dil.map")
    environment: str = Field(default="local")
    log_level: str = Field(default="INFO")
    assets_dir: Path = Field(default=DEFAULT_ASSETS_DIR)

    # Database settings
    database_url: str = Field(default="postgresql://postgres:postgres@localhost:5432/tv_api")
    
    # Email settings
    smtp_host: str = Field(default="smtp.gmail.com")
    smtp_port: int = Field(default=587)
    smtp_username: str = Field(default="")
    smtp_password: str = Field(default="")
    smtp_from_email: str = Field(default="noreply@dilly.cloud")
    smtp_from_name: str = Field(default="dil.map")
    
    # Magic link settings
    magic_link_base_url: str = Field(default="https://tv.dilly.cloud/auth/verify")
    magic_link_expiry_minutes: int = Field(default=15)
    
    # Rate limiting
    rate_limit_per_email_per_hour: int = Field(default=3)
    rate_limit_per_ip_per_hour: int = Field(default=10)
    
    # Shopify webhook settings
    shopify_webhook_secret: str = Field(default="")

    model_config = SettingsConfigDict(
        env_prefix="TV_API_", 
        case_sensitive=False,
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
    )


@lru_cache
def get_settings() -> Settings:
    """Return a cached settings object so expensive IO only runs once."""

    return Settings()
