resource "google_firestore_database" "main" {
  project     = var.project_id
  name        = "(default)"
  location_id = var.region
  type        = "FIRESTORE_NATIVE"

  # Prevent accidental deletion of the database
  deletion_policy = "DELETE"

  depends_on = [google_project_service.services]
}

# Composite index: jobs collection — status + relevance_score (for filtered queries)
resource "google_firestore_index" "jobs_status_score" {
  project    = var.project_id
  database   = google_firestore_database.main.name
  collection = "jobs"

  fields {
    field_path = "status"
    order      = "ASCENDING"
  }

  fields {
    field_path = "relevance_score"
    order      = "DESCENDING"
  }

  depends_on = [google_firestore_database.main]
}

# Composite index: applications — status + created_at (for filtered listing)
resource "google_firestore_index" "apps_status_created" {
  project    = var.project_id
  database   = google_firestore_database.main.name
  collection = "applications"

  fields {
    field_path = "status"
    order      = "ASCENDING"
  }

  fields {
    field_path = "created_at"
    order      = "DESCENDING"
  }

  depends_on = [google_firestore_database.main]
}

