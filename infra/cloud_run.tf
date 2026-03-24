resource "google_service_account" "cloud_run" {
  account_id   = "applybot-run"
  display_name = "ApplyBot Cloud Run"
}

# Cloud SQL Client role
resource "google_project_iam_member" "cloud_run_sql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

# Secret Manager accessor
resource "google_project_iam_member" "cloud_run_secrets" {
  project = var.project_id
  role    = "roles/secretmanager.secretAccessor"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

locals {
  cloud_sql_connection = "${var.project_id}:${var.region}:${google_sql_database_instance.main.name}"
  image_uri            = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.applybot.repository_id}/applybot:${var.image_tag}"
  database_url         = "postgresql+psycopg://applybot:${var.db_password}@/applybot?host=/cloudsql/${local.cloud_sql_connection}"
}

resource "google_cloud_run_v2_service" "applybot" {
  name     = "applybot"
  location = var.region

  deletion_protection = false

  template {
    service_account = google_service_account.cloud_run.email

    scaling {
      min_instance_count = 0
      max_instance_count = 1
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [local.cloud_sql_connection]
      }
    }

    containers {
      image = local.image_uri

      ports {
        container_port = 8000
      }

      env {
        name  = "DATABASE_URL"
        value = local.database_url
      }

      env {
        name = "ANTHROPIC_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.anthropic_api_key.secret_id
            version = "latest"
          }
        }
      }

      dynamic "env" {
        for_each = var.serpapi_key != "" ? [1] : []
        content {
          name = "SERPAPI_KEY"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.serpapi_key.secret_id
              version = "latest"
            }
          }
        }
      }

      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }

      startup_probe {
        http_get {
          path = "/healthz"
        }
        initial_delay_seconds = 10
        period_seconds        = 5
        failure_threshold     = 6
      }

      liveness_probe {
        http_get {
          path = "/healthz"
        }
        period_seconds = 30
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }
  }

  depends_on = [
    google_project_service.services,
    google_project_iam_member.cloud_run_sql,
    google_project_iam_member.cloud_run_secrets,
  ]
}

# Allow unauthenticated access (public dashboard)
resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.applybot.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
