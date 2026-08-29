resource "google_service_account" "cloud_run" {
  account_id   = "applybot-run"
  display_name = "ApplyBot Cloud Run"
}

# Firestore access for Cloud Run
resource "google_project_iam_member" "cloud_run_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.cloud_run.email}"
}

# Secret Manager access — scoped per secret, not project-wide.
#
# secretAccessor: read access for secrets bound via secret_key_ref (serpapi,
#   dashboard-totp) and for the per-provider LLM keys mounted as volumes and
#   read by applybot.llm.client on each completion.
resource "google_secret_manager_secret_iam_member" "cloud_run_secret_accessor" {
  # Keyed by static names (not secret `.id`s) because the per-provider
  # secrets do not exist until the first apply, and a for_each set cannot
  # contain values that are only known after apply.
  for_each = {
    serpapi   = google_secret_manager_secret.serpapi_key.id
    totp      = google_secret_manager_secret.dashboard_totp_secret.id
    openai    = google_secret_manager_secret.llm_provider_key["openai"].id
    anthropic = google_secret_manager_secret.llm_provider_key["anthropic"].id
    gemini    = google_secret_manager_secret.llm_provider_key["gemini"].id
    glm       = google_secret_manager_secret.llm_provider_key["glm"].id
  }
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.cloud_run.email}"
}

# secretVersionAdder: write access so update_provider() / delete_provider() can
# add new key versions at runtime (near-real-time key rotation across services).
resource "google_secret_manager_secret_iam_member" "cloud_run_secret_adder" {
  for_each  = google_secret_manager_secret.llm_provider_key
  secret_id = each.value.id
  role      = "roles/secretmanager.secretVersionAdder"
  member    = "serviceAccount:${google_service_account.cloud_run.email}"
}

# GCS bucket access for Cloud Run
resource "google_storage_bucket_iam_member" "cloud_run_storage" {
  bucket = google_storage_bucket.data.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.cloud_run.email}"
}

locals {
  image_uri = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.applybot.repository_id}/applybot:${var.image_tag}"
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

    containers {
      image = local.image_uri

      ports {
        container_port = 8000
      }

      # Provider API keys: volume-mounted (not env-bound) so key rotations
      # written to Secret Manager by update_provider() reach this service
      # without a new revision -- the platform refreshes the mounts. Each
      # secret mounts as a directory of version files incl. a `latest` entry,
      # which is what applybot.llm.client reads.
      dynamic "volume_mounts" {
        for_each = local.llm_secret_ids
        content {
          name       = volume_mounts.value
          mount_path = "/etc/secrets/${volume_mounts.value}"
        }
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "GCS_BUCKET_NAME"
        value = google_storage_bucket.data.name
      }

      env {
        name  = "DISCOVERY_FUNCTION_URL"
        value = google_cloudfunctions2_function.discovery.url
      }
      # env {
      #   name  = "APPLICATION_PREPARER_FUNCTION_URL"
      #   value = google_cloudfunctions2_function.preparer.url
      # }

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

      env {
        name = "DASHBOARD_TOTP_SECRET"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.dashboard_totp_secret.secret_id
            version = "latest"
          }
        }
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

    # One secret volume per provider key; no version items pinned, so the
    # mount materializes every version plus `latest` and follows new versions.
    dynamic "volumes" {
      for_each = local.llm_secret_ids
      content {
        name = volumes.value
        secret {
          secret = google_secret_manager_secret.llm_provider_key[volumes.key].id
        }
      }
    }
  }

  depends_on = [
    google_project_service.services,
    google_project_iam_member.cloud_run_firestore,
    google_secret_manager_secret_iam_member.cloud_run_secret_accessor,
    google_secret_manager_secret_iam_member.cloud_run_secret_adder,
    google_storage_bucket_iam_member.cloud_run_storage,
  ]

  lifecycle {
    # Image updates are deployed via gcloud run deploy in the Docker workflow.
    # Terraform manages service config only; ignore image changes to prevent drift.
    ignore_changes = [template[0].containers[0].image]
  }
}

# Allow unauthenticated access (public dashboard)
resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.applybot.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
