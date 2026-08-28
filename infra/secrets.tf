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
# Per-provider LLM API keys.
#
# secret_id values MUST match the ids hardcoded in
# applybot.llm.providers.LLMProvider (openai-api-key / anthropic-api-key /
# gemini-api-key / glm-api-key). The store layer reads keys live from Secret Manager on each
# cache miss (not via Cloud Run secret_key_ref, which only resolves at
# cold-start), so keys can be rotated at runtime by update_provider().
#
# The secret shells are created unconditionally; versions are seeded only when a
# key is supplied at deploy time. `count` (not for_each) gates the version
# resources because the key values are sensitive and Terraform forbids sensitive
# values in for_each arguments.
# ---------------------------------------------------------------------------

locals {
  # Non-sensitive: provider -> secret id (must match applybot.llm.providers).
  llm_provider_secret_ids = {
    openai    = "openai-api-key"
    anthropic = "anthropic-api-key"
    gemini    = "gemini-api-key"
    glm       = "glm-api-key"
  }
}

resource "google_secret_manager_secret" "llm_provider_key" {
  for_each  = local.llm_provider_secret_ids
  secret_id = each.value

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
