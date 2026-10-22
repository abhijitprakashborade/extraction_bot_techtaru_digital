"""
Configuration Management
Pydantic-Settings reads from .env automatically — type-safe, validated at startup.

When OPENAI_API_KEY is empty, the app automatically falls back to the built-in
deterministic heuristic engine so the demo never hard-fails (see
services/heuristic_engine.py).
"""
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List


class Settings(BaseSettings):
    # ─── App ──────────────────────────────────────────────
    app_name: str = "TechTaru DocIQ"
    app_version: str = "3.0.0"
    debug: bool = False
    allowed_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ─── OpenAI Structured Outputs ────────────────────────
    openai_api_key: str = ""                # empty → heuristic demo engine
    openai_model: str = "gpt-4o-mini"       # fast + cheap; swap to gpt-4o if needed
    max_tokens: int = 4096
    llm_timeout_seconds: float = 90.0
    max_retries: int = 3                    # For 429 / 5xx handling
    retry_base_delay: float = 1.0           # Exponential backoff base

    # ─── File Processing ───────────────────────────────────
    max_file_size_mb: int = 10
    supported_extensions: List[str] = [".pdf", ".docx", ".txt", ".png", ".jpg", ".jpeg"]

    # ─── Database ──────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./extraction_history.db"

    # ─── Rate Limiting ─────────────────────────────────────
    rate_limit_per_minute: int = 20         # per client IP on /extract endpoints

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
