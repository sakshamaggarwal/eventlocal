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

    # --- LLM (Groq primary + OpenRouter failover) ---
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    llm_model: str = "qwen3-32b"
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_temperature: float = 0.7
    llm_max_tokens: int = 4096

    # --- OpenRouter (failover, FREE models only) ---
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    # IMPORTANT: Only free models allowed. The :free suffix is required.
    openrouter_model: str = "qwen/qwen3-32b:free"

    # --- Event Sources ---
    luma_api_key: str = Field(default="", alias="LUMA_API_KEY")
    eventbrite_api_key: str = Field(default="", alias="EVENTBRITE_API_KEY")
    google_places_api_key: str = Field(default="", alias="GOOGLE_PLACES_API_KEY")
    ticketmaster_api_key: str = Field(default="", alias="TICKETMASTER_API_KEY")
    yelp_api_key: str = Field(default="", alias="YELP_API_KEY")  # deferred — not wired into active pipeline yet
    seatgeek_client_id: str = Field(default="", alias="SEATGEEK_CLIENT_ID")

    # --- Cognee (Knowledge Graph) ---
    cognee_llm_api_key: str = Field(default="", alias="COGNEE_LLM_API_KEY")
    cognee_vector_db: str = Field(default="lancedb", alias="COGNEE_VECTOR_DB")
    cognee_graph_db: str = Field(default="networkx", alias="COGNEE_GRAPH_DB")

    # --- Supabase (Database & Auth) ---
    supabase_url: str = Field(default="", alias="SUPABASE_URL")
    supabase_key: str = Field(default="", alias="SUPABASE_KEY")

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
