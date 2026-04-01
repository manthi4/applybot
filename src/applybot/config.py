from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM provider — "gemini" (Vertex AI) or "anthropic" (Vertex AI)
    llm_provider: Literal["gemini", "anthropic"] = "gemini"

    # Shared Vertex AI settings (both providers use Google ADC auth)
    vertex_region: str = "us-east5"

    # Gemini (Vertex AI)
    gemini_model_fast: str = "gemini-2.0-flash"
    gemini_model_smart: str = "gemini-2.5-pro"

    # Anthropic / Claude (Vertex AI)
    anthropic_model_fast: str = "claude-sonnet-4-6"
    anthropic_model_smart: str = "claude-sonnet-4-6"
    anthropic_max_retries: int = 3

    # Job scraping
    serpapi_key: str = ""

    # Google / GCP
    gcp_project_id: str = ""
    gcs_bucket_name: str = ""  # GCS bucket for file storage (resumes, etc.)

    # Google / Gmail
    google_application_credentials: str = ""

    # Server
    port: int = 8000

    # Dashboard auth (TOTP — use `applybot setup-auth` to generate and scan QR code)
    dashboard_totp_secret: str = ""

    # Discovery
    discovery_relevance_threshold: int = 50
    discovery_max_jobs_per_run: int = 100

    # Application
    max_applications_per_day: int = 10


settings = Settings()
