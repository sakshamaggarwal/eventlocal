"""
eventlocal configuration — loads from .env, provides typed settings.
"""
from __future__ import annotations

import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings

_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Validated app settings. Reads .env automatically."""

    # --- LLM (Groq + Qwen3-32B) ---
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    llm_model: str = "qwen3-32b"
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096

    # --- Event Sources ---
    luma_api_key: str = Field(default="", alias="LUMA_API_KEY")
    eventbrite_api_key: str = Field(default="", alias="EVENTBRITE_API_KEY")
    google_places_api_key: str = Field(default="", alias="GOOGLE_PLACES_API_KEY")

    # --- TriggerWare ---
    triggerware_url: str = Field(default="", alias="TRIGGERWARE_URL")
    triggerware_api_key: str = Field(default="", alias="TRIGGERWARE_API_KEY")

    # --- App ---
    app_env: str = "development"
    app_port: int = 8000
    city: str = "bay-area"

    model_config = {
        "env_file": str(_ROOT / ".env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


# Singleton
settings = Settings()
