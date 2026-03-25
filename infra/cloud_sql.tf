# Cloud SQL instance — deletion_protection disabled so it can be removed.
# TODO: Delete this entire file after the next successful terraform apply to destroy the instance.
resource "google_sql_database_instance" "main" {
  name             = "applybot-db"
  database_version = "POSTGRES_15"
  region           = var.region

  settings {
    tier              = "db-f1-micro"
    edition           = "ENTERPRISE"
    availability_type = "ZONAL"

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = false
    }

    ip_configuration {
      ipv4_enabled = true
    }
  }

  deletion_protection = false

  depends_on = [google_project_service.services]
}
