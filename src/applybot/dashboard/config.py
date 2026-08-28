"""
Values are loaded **only** from real environment variables.
Intended for the containerized dashboard (``docker-compose`` / Cloud Run),
where every setting is injected as an environment variable and no ``.env``
file exists on disk.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Dashboard settings sourced from the environment only (no ``.env``)."""

    model_config = SettingsConfigDict(
        env_file=None,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Google / GCP
    gcp_project_id: str = ""
    gcs_bucket_name: str = ""  # GCS bucket for file storage (resumes, etc.)

    # Google / Gmail
    google_application_credentials: str = ""

    # Server
    port: int = 8000

    # Dashboard auth (TOTP — use `applybot setup-auth` to generate and scan QR code)
    dashboard_totp_secret: str = ""

    # Discovery — URL of the deployed discovery Cloud Function (infra/cloud_functions.tf).
    # The dashboard triggers discovery over HTTP rather than importing the pipeline.
    discovery_function_url: str = ""

    # Application preparer — URL of the deployed application-preparer Cloud Function.
    # The dashboard triggers application preparation over HTTP rather than importing
    # the preparer (mirror of the discovery function pattern).
    application_preparer_function_url: str = ""

settings = Settings()
