from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    claimsight_env: str = "dev"
    claimsight_cors_origins: str = "http://localhost:5173,http://localhost:8080"
    database_url: str = "sqlite+pysqlite:///./claimsight.db"
    demo_auth: bool = True
    claimsight_token_budget: int = 8000
    claimsight_high_value_usd: float = 50000
    celery_broker_url: str = "redis://localhost:6379/1"
    claimsight_async: bool = False
    claimsight_rate_limit: int = 0

    @property
    def cors_list(self) -> list[str]:
        return [s.strip() for s in self.claimsight_cors_origins.split(",") if s.strip()]


settings = Settings()
