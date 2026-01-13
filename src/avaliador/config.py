"""
Configuration management for Avaliador de MITs.

Uses pydantic-settings to load configuration from environment variables and .env files.
"""

from pathlib import Path
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # DTA Proxy Configuration
    dta_proxy_api_key: str = Field(
        default="",
        description="API Key for DTA Proxy authentication",
    )
    dta_proxy_base_url: str = Field(
        default="https://proxy.dta.totvs.ai",
        description="Base URL for DTA Proxy",
    )

    # Model Configuration
    dta_model: str = Field(
        default="gemini-2.5-pro",
        description="Model to use for text and vision analysis",
    )

    # Cache Configuration
    cache_enabled: bool = Field(
        default=True,
        description="Enable caching of document extractions",
    )
    cache_dir: Path = Field(
        default=Path.home() / ".cache" / "avaliador",
        description="Directory for cache storage",
    )

    # Logging Configuration
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )

    # Vision Configuration
    vision_enabled: bool = Field(
        default=True,
        description="Enable vision analysis for diagrams",
    )

    # Timeout Configuration
    llm_timeout: int = Field(
        default=120,
        description="Timeout in seconds for LLM calls",
    )
    vision_timeout: int = Field(
        default=60,
        description="Timeout in seconds for vision analysis",
    )

    @field_validator("cache_dir", mode="before")
    @classmethod
    def expand_cache_dir(cls, v: str | Path) -> Path:
        """Expand ~ in cache directory path."""
        if isinstance(v, str):
            return Path(v).expanduser()
        return v.expanduser()

    @field_validator("log_level", mode="before")
    @classmethod
    def uppercase_log_level(cls, v: str) -> str:
        """Ensure log level is uppercase."""
        return v.upper() if isinstance(v, str) else v

    @property
    def is_configured(self) -> bool:
        """Check if the application is properly configured."""
        return bool(self.dta_proxy_api_key)

    def ensure_cache_dir(self) -> Path:
        """Ensure cache directory exists and return its path."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        return self.cache_dir


# Global settings instance
settings = Settings()
