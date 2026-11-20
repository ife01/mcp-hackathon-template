"""Server configuration loaded from environment variables or a .env file.

Every field can be overridden by an environment variable of the same name
(upper- or lower-case). Copy `.env.example` to `.env` for local development.
"""

from __future__ import annotations

import logging

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Respiratory MCP server settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Transport ──────────────────────────────────────────────────────────
    mcp_transport: str = "stdio"
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8000

    # ── Socrata / CDC API ──────────────────────────────────────────────────
    # Optional free app token from https://dev.socrata.com/foundry/
    # Raises rate limits from ~1 req/s (anonymous) to ~10 req/s (token).
    socrata_app_token: str = ""

    # ── Cache ──────────────────────────────────────────────────────────────
    # How long to cache Socrata responses in memory (seconds).
    cache_ttl_seconds: int = 3600

    # ── HTTP client ────────────────────────────────────────────────────────
    http_timeout_seconds: int = 15

    # ── Security: outbound domain allowlist ───────────────────────────────
    # Only these hosts may be contacted by the Socrata client.
    # Must be an exact-match list (no wildcards).
    allowed_domains: list[str] = ["data.cdc.gov", "api.us.socrata.com"]

    # ── Logging ────────────────────────────────────────────────────────────
    log_level: str = "INFO"

    @field_validator("log_level")
    @classmethod
    def _validate_log_level(cls, v: str) -> str:
        level = v.upper()
        if level not in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"):
            raise ValueError(f"Invalid log level: {v!r}")
        return level


settings = Settings()


def configure_logging() -> None:
    """Configure root logger to write to stderr at the configured level.

    Must be called once at startup (before any other logging). MCP stdio
    transport uses stdout for protocol messages — logging MUST go to stderr.
    """
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    # Silence noisy third-party loggers at WARNING unless we're in DEBUG.
    if settings.log_level != "DEBUG":
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
