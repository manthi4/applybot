from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    anthropic_api_key: str = ""
    anthropic_model_fast: str = "claude-sonnet-4-20250514"
    anthropic_model_smart: str = "claude-sonnet-4-20250514"
    anthropic_max_retries: int = 3

    # Job scraping
    serpapi_key: str = ""

    # Database
    database_url: str = "sqlite:///data/applybot.db"

    # Google / Gmail
    google_application_credentials: str = ""

    # Server
    port: int = 8000

    # Discovery
    discovery_relevance_threshold: int = 50
    discovery_max_jobs_per_run: int = 100

    # Application
    max_applications_per_day: int = 10


settings = Settings()
