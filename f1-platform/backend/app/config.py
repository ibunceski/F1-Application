from typing import Literal

from pydantic import computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    API_KEY: str | None = None
    ENVIRONMENT: Literal["development", "production", "test"] = "development"
    FASTF1_CACHE_PATH: str = "/app/cache"
    MODELS_STORE_PATH: str = "/app/models_store"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    API_V1_PREFIX: str = "/api/v1"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @computed_field
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        if self.DATABASE_URL.startswith("postgresql+asyncpg://"):
            return self.DATABASE_URL
        if self.DATABASE_URL.startswith("postgresql://"):
            return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
        return self.DATABASE_URL


settings = Settings()
