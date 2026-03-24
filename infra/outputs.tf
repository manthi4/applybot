output "dashboard_url" {
  description = "URL of the deployed ApplyBot dashboard"
  value       = google_cloud_run_v2_service.applybot.uri
}

output "cloud_sql_connection_name" {
  description = "Cloud SQL connection name for proxy"
  value       = google_sql_database_instance.main.connection_name
}

output "artifact_registry" {
  description = "Docker image registry URL"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.applybot.repository_id}"
}
