output "dashboard_url" {
  description = "URL of the deployed ApplyBot dashboard"
  value       = google_cloud_run_v2_service.applybot.uri
}

output "data_bucket" {
  description = "GCS bucket used for file storage (resumes, exports)"
  value       = google_storage_bucket.data.name
}

output "artifact_registry" {
  description = "Docker image registry URL"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.applybot.repository_id}"
}

output "discovery_function_url" {
  description = "URL of the discovery Cloud Function"
  value       = google_cloudfunctions2_function.discovery.url
}
