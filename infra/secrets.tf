resource "google_secret_manager_secret" "serpapi_key" {
  secret_id = "serpapi-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.services]
}

resource "google_secret_manager_secret_version" "serpapi_key" {
  count       = var.serpapi_key != "" ? 1 : 0
  secret      = google_secret_manager_secret.serpapi_key.id
  secret_data = var.serpapi_key
}

resource "google_secret_manager_secret" "dashboard_totp_secret" {
  secret_id = "dashboard-totp-secret"

  replication {
    auto {}
  }

  depends_on = [google_project_service.services]
}

resource "google_secret_manager_secret_version" "dashboard_totp_secret" {
  secret      = google_secret_manager_secret.dashboard_totp_secret.id
  secret_data = var.dashboard_totp_secret
}
