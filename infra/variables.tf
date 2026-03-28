variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region (for Cloud Run, Artifact Registry, GCS, etc.)"
  type        = string
  default     = "us-central1"
}

variable "vertex_region" {
  description = "Vertex AI region for Claude model access (must support the model — claude-sonnet-4-6 requires us-east5, europe-west1, or asia-southeast1)"
  type        = string
  default     = "us-east5"
}

variable "serpapi_key" {
  description = "SerpAPI key"
  type        = string
  sensitive   = true
  default     = ""
}

variable "image_tag" {
  description = "Docker image tag to deploy"
  type        = string
  default     = "latest"
}

variable "dashboard_totp_secret" {
  description = "Base32 TOTP secret for dashboard auth (generate with: python -c 'import pyotp; print(pyotp.random_base32())')"
  type        = string
  sensitive   = true
}
