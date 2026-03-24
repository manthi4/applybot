# --- GCS bucket for function source code ---
resource "google_storage_bucket" "gcf_source" {
  name     = "${var.project_id}-gcf-source"
  location = var.region

  uniform_bucket_level_access = true

  depends_on = [google_project_service.services]
}

# --- Archive function source ---
data "archive_file" "discovery_source" {
  type        = "zip"
  output_path = "${path.module}/.terraform/tmp/discovery-source.zip"
  source_dir  = "${path.module}/.."
  excludes = [
    ".venv",
    ".git",
    "data",
    "infra",
    "tests",
    "alembic",
    ".mypy_cache",
    "__pycache__",
    ".ruff_cache",
    ".pytest_cache",
    "*.egg-info",
    ".env",
  ]
}

# --- Upload source to GCS ---
resource "google_storage_bucket_object" "discovery_source" {
  name   = "discovery-source-${data.archive_file.discovery_source.output_md5}.zip"
  bucket = google_storage_bucket.gcf_source.name
  source = data.archive_file.discovery_source.output_path
}

# --- TCP DATABASE_URL for Cloud Functions (no Cloud SQL socket mount available) ---
locals {
  # Cloud Functions Gen 2 does not support Cloud SQL volume mounts like Cloud Run.
  # Uses a direct TCP connection to Cloud SQL's public IP instead.
  # TODO: Replace with VPC connector + private IP for production hardening.
  discovery_database_url = "postgresql+psycopg://applybot:${var.db_password}@${google_sql_database_instance.main.public_ip_address}/applybot"
}

# --- Cloud Function Gen 2 ---
resource "google_cloudfunctions2_function" "discovery" {
  name     = "applybot-discovery"
  location = var.region

  build_config {
    runtime     = "python312"
    entry_point = "handle_discovery"

    source {
      storage_source {
        bucket = google_storage_bucket.gcf_source.name
        object = google_storage_bucket_object.discovery_source.name
      }
    }
  }

  service_config {
    max_instance_count    = 1
    available_memory      = "512Mi"
    timeout_seconds       = 300
    service_account_email = google_service_account.cloud_run.email

    environment_variables = {
      DATABASE_URL = local.discovery_database_url
    }

    secret_environment_variables {
      key        = "ANTHROPIC_API_KEY"
      project_id = var.project_id
      secret     = google_secret_manager_secret.anthropic_api_key.secret_id
      version    = "latest"
    }

    secret_environment_variables {
      key        = "SERPAPI_KEY"
      project_id = var.project_id
      secret     = google_secret_manager_secret.serpapi_key.secret_id
      version    = "latest"
    }
  }

  depends_on = [
    google_project_service.services,
    google_project_iam_member.cloud_run_sql,
    google_project_iam_member.cloud_run_secrets,
  ]
}

# --- Cloud Scheduler job ---
resource "google_cloud_scheduler_job" "discovery" {
  name      = "applybot-discovery"
  schedule  = var.discovery_schedule
  time_zone = "UTC"

  http_target {
    http_method = "POST"
    uri         = google_cloudfunctions2_function.discovery.url

    oidc_token {
      service_account_email = google_service_account.cloud_run.email
    }
  }

  depends_on = [google_project_service.services]
}

# --- Allow the service account to invoke the function ---
resource "google_cloudfunctions2_function_iam_member" "scheduler_invoker" {
  project        = var.project_id
  location       = var.region
  cloud_function = google_cloudfunctions2_function.discovery.name
  role           = "roles/cloudfunctions.invoker"
  member         = "serviceAccount:${google_service_account.cloud_run.email}"
}

# --- Allow the service account to generate OIDC tokens for itself (for Scheduler) ---
resource "google_service_account_iam_member" "scheduler_token_creator" {
  service_account_id = google_service_account.cloud_run.name
  role               = "roles/iam.serviceAccountTokenCreator"
  member             = "serviceAccount:${google_service_account.cloud_run.email}"
}
