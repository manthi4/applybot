from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM (Vertex AI)
    vertex_model_fast: str = "claude-sonnet-4-6-20260301"
    vertex_model_smart: str = "claude-sonnet-4-6-20260301"
    vertex_max_retries: int = 3
    vertex_region: str = "us-east5"

    # Job scraping
    serpapi_key: str = ""

    # Google / GCP
    gcp_project_id: str = ""

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
