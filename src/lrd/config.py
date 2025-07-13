"""App settings (env / .env)."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # LLM under test (Groq)
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    # Judge + embeddings (Gemini)
    google_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_embed_model: str = "gemini-embedding-001"

    # Where ml-research-agent lives (used by the MlraPlannerSUT)
    mlra_path: str = "../ml-research-agent"

    # Slack — leave empty to simulate (write JSON to alerts/) for the demo
    slack_webhook_url: str = ""


settings = Settings()
