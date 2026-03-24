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

  deletion_protection = true

  depends_on = [google_project_service.services]
}

resource "google_sql_database" "applybot" {
  name     = "applybot"
  instance = google_sql_database_instance.main.name
}

resource "google_sql_user" "applybot" {
  name     = "applybot"
  instance = google_sql_database_instance.main.name
  password = var.db_password
}
