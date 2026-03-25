resource "google_storage_bucket" "data" {
  name          = "${var.project_id}-applybot-data"
  location      = var.region
  force_destroy = false

  uniform_bucket_level_access = true

  depends_on = [google_project_service.services]
}
