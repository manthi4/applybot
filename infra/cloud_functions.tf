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
      GCP_PROJECT_ID = var.project_id
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
    google_project_iam_member.cloud_run_firestore,
    google_project_iam_member.cloud_run_secrets,
  ]
}

# --- Allow the service account to invoke the function ---
resource "google_cloudfunctions2_function_iam_member" "scheduler_invoker" {
  project        = var.project_id
  location       = var.region
  cloud_function = google_cloudfunctions2_function.discovery.name
  role           = "roles/cloudfunctions.invoker"
  member         = "serviceAccount:${google_service_account.cloud_run.email}"
}
