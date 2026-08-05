variable "project_id" {
  description = "GCP project ID"
  type        = string
}

variable "region" {
  description = "GCP region (for Cloud Run, Artifact Registry, GCS, etc.)"
  type        = string
  default     = "us-central1"
}

variable "llm_model_fast" {
  description = "litellm model string for the 'fast' tier. The prefix selects the provider (gpt-* = OpenAI, claude-* = Anthropic, gemini/* = Google)."
  type        = string
  default     = "gpt-4o-mini"
}

variable "llm_model_smart" {
  description = "litellm model string for the 'smart' tier. The prefix selects the provider."
  type        = string
  default     = "gpt-4o"
}

variable "llm_api_key" {
  description = "API key for the configured LLM provider. Injected under the env var named by llm_api_key_env_name (e.g. OPENAI_API_KEY)."
  type        = string
  sensitive   = true
  default     = ""
}

variable "llm_api_key_env_name" {
  description = "Env var name litellm expects the provider API key under: OPENAI_API_KEY, ANTHROPIC_API_KEY, or GEMINI_API_KEY."
  type        = string
  default     = "OPENAI_API_KEY"
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
