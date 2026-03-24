resource "google_artifact_registry_repository" "applybot" {
  location      = var.region
  repository_id = "applybot"
  format        = "DOCKER"
  description   = "ApplyBot Docker images"

  depends_on = [google_project_service.services]
}
