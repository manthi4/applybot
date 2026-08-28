variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region (for Cloud Run, Artifact Registry, GCS, etc.)"
  type        = string
  default     = "us-central1"
}

variable "openai_api_key" {
  description = "OpenAI API key. Stored in Secret Manager secret openai-api-key; read live by applybot.llm.client. Leave blank to seed via update_provider() at runtime."
  type        = string
  sensitive   = true
  default     = ""
}

variable "anthropic_api_key" {
  description = "Anthropic API key. Stored in Secret Manager secret anthropic-api-key; read live by applybot.llm.client. Leave blank to seed via update_provider() at runtime."
  type        = string
  sensitive   = true
  default     = ""
}

variable "gemini_api_key" {
  description = "Google Gemini API key. Stored in Secret Manager secret gemini-api-key; read live by applybot.llm.client. Leave blank to seed via update_provider() at runtime."
  type        = string
  sensitive   = true
  default     = ""
}

variable "glm_api_key" {
  description = "Z.AI (GLM) API key, env var ZAI_API_KEY. Stored in Secret Manager secret glm-api-key; read live by applybot.llm.client. Leave blank to seed via update_provider() at runtime."
  type        = string
  sensitive   = true
  default     = ""
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
