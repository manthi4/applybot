resource "google_secret_manager_secret" "serpapi_key" {
  secret_id = "serpapi-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.services]
}

resource "google_secret_manager_secret_version" "serpapi_key" {
  count       = var.serpapi_key != "" ? 1 : 0
  secret      = google_secret_manager_secret.serpapi_key.id
  secret_data = var.serpapi_key
}

resource "google_secret_manager_secret" "dashboard_totp_secret" {
  secret_id = "dashboard-totp-secret"

  replication {
    auto {}
  }

  depends_on = [google_project_service.services]
}

resource "google_secret_manager_secret_version" "dashboard_totp_secret" {
  secret      = google_secret_manager_secret.dashboard_totp_secret.id
  secret_data = var.dashboard_totp_secret
}

# ---------------------------------------------------------------------------
# Per-provider LLM API keys. Secret ids must match applybot.llm.providers.
# LLMProvider. Shells are created unconditionally; versions are seeded only
# when a key var is supplied. Versions use `count` (not for_each) because
# Terraform forbids sensitive values in for_each.
# ---------------------------------------------------------------------------

locals {
  # Provider slugs must match applybot.llm.providers.LLMProvider;
  # secret ids follow the "<slug>-api-key" convention.
  llm_providers = toset(["openai", "anthropic", "gemini", "glm"])

  # Secret id per slug (static strings): used by the IAM grants and the volume
  # mounts in cloud_run.tf / cloud_functions.tf, whose for_each keys must be
  # known at plan time -- the secrets' `.id`s are not, until the first apply
  # creates them.
  llm_secret_ids = { for slug in local.llm_providers : slug => "${slug}-api-key" }
}

resource "google_secret_manager_secret" "llm_provider_key" {
  for_each  = local.llm_providers
  secret_id = "${each.value}-api-key"

  replication {
    auto {}
  }

  depends_on = [google_project_service.services]
}

resource "google_secret_manager_secret_version" "openai_api_key" {
  count       = var.openai_api_key != "" ? 1 : 0
  secret      = google_secret_manager_secret.llm_provider_key["openai"].id
  secret_data = var.openai_api_key
}

resource "google_secret_manager_secret_version" "anthropic_api_key" {
  count       = var.anthropic_api_key != "" ? 1 : 0
  secret      = google_secret_manager_secret.llm_provider_key["anthropic"].id
  secret_data = var.anthropic_api_key
}

resource "google_secret_manager_secret_version" "gemini_api_key" {
  count       = var.gemini_api_key != "" ? 1 : 0
  secret      = google_secret_manager_secret.llm_provider_key["gemini"].id
  secret_data = var.gemini_api_key
}

resource "google_secret_manager_secret_version" "glm_api_key" {
  count       = var.glm_api_key != "" ? 1 : 0
  secret      = google_secret_manager_secret.llm_provider_key["glm"].id
  secret_data = var.glm_api_key
}
