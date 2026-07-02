"""Application settings, loaded from environment (see .env.example).

Everything configurable lives here so no module reaches into os.environ directly.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FINOS_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- Core ----
    env: Literal["dev", "test", "staging", "prod"] = "dev"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "http://localhost:3000"

    # ---- Data stores ----
    database_url: str = "postgresql+asyncpg://finos:finos@localhost:5432/finos"
    redis_url: str = "redis://localhost:6379/0"

    # ---- Object storage ----
    s3_endpoint: str = "http://localhost:9000"
    s3_bucket: str = "finos-attachments"
    s3_access_key: str = "finos"
    s3_secret_key: str = "finos"

    # ---- Auth (Supabase as identity provider only) ----
    supabase_url: str = ""
    supabase_jwks_url: str = ""
    jwt_audience: str = "authenticated"
    auth_dev_bypass: bool = True

    # ---- AI (optional) ----
    ai_enabled: bool = False
    ai_provider: Literal["anthropic", "openai"] = "anthropic"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    ai_monthly_budget_minor: int = Field(default=0, ge=0)

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
