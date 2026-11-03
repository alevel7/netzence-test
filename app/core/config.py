import json
from functools import lru_cache
from typing import Any, List, Union

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables and .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    APP_NAME: str = "Production FastAPI Service"
    APP_VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    APP_WORKERS: int = 1
    API_V1_PREFIX: str = "/api/v1"

    # Security
    SECRET_KEY: str = "your-secret-key"  # Replace with a secure random key in production
    CORS_ORIGINS: Union[List[str], str] = ["*"]

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except json.JSONDecodeError:
                    pass
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, set)):
            return list(v)
        return ["*"]

    # PostgreSQL Database
    POSTGRES_SERVER: str = "db"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "postgres"
    POSTGRES_DB: str = "app_db"
    
    # DB Pool Configuration
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 1800

    @property
    def resolved_postgres_server(self) -> str:
        """Resolves the active postgres hostname with fallback for container aliases."""
        import socket
        for candidate in [self.POSTGRES_SERVER, "db", "fastapi_postgres"]:
            if not candidate:
                continue
            try:
                socket.gethostbyname(candidate)
                return candidate
            except Exception:
                continue
        return self.POSTGRES_SERVER

    @property
    def async_database_url(self) -> str:
        """Constructs async PostgreSQL connection URL using asyncpg."""
        server = self.resolved_postgres_server
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{server}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def sync_database_url(self) -> str:
        """Constructs synchronous PostgreSQL connection URL for Alembic or sync tools."""
        server = self.resolved_postgres_server
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{server}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # Redis Cache & Messaging
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0
    REDIS_CACHE_EXPIRE_SECONDS: int = 300

    @property
    def resolved_redis_host(self) -> str:
        """Resolves the active redis hostname with fallback for container aliases."""
        import socket
        for candidate in [self.REDIS_HOST, "redis", "fastapi_redis"]:
            if not candidate:
                continue
            try:
                socket.gethostbyname(candidate)
                return candidate
            except Exception:
                continue
        return self.REDIS_HOST

    @property
    def redis_url(self) -> str:
        """Constructs Redis connection URL."""
        host = self.resolved_redis_host
        if self.REDIS_PASSWORD:
            return f"redis://:{self.REDIS_PASSWORD}@{host}:{self.REDIS_PORT}/{self.REDIS_DB}"
        return f"redis://{host}:{self.REDIS_PORT}/{self.REDIS_DB}"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # "json" or "text"


@lru_cache()
def get_settings() -> Settings:
    """Returns cached settings instance."""
    return Settings()


settings = get_settings()

