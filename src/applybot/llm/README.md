# LLM

Provider-agnostic LLM client backed by [litellm](https://github.com/BerriAI/litellm),
so swapping the underlying model is a config change, not a code change — no vendor lock-in.

## Files
- **providers.py** — `LLMProvider` enum, per-provider metadata, and model-prefix routing (leaf: no runtime state, easy to extend)
- **_backends.py** — GCP I/O shims: Secret Manager (API keys) and Firestore (default model)
- **client.py** — the public API: TTL caches, runtime-mutable provider/model stores, and `complete()` (no singleton, no `config.py`)

## Design: runtime-mutable config

Provider API keys and the default model are **mutable while the app is deployed** (the
set of providers itself is a code edit in `providers.py`). There is deliberately no
`config.py` / settings object — these values change at runtime, so every value is read
fresh from the environment or its backing store on each access.

- **API keys** live in **GCP Secret Manager** (one secret per provider).
- **Default model** lives in a **Firestore** document (`config/llm` → `default_model`).
  Model names are not secret, so Firestore — not Secret Manager — is the right store.

Both are read through a short-TTL in-process cache (~30 s), so every service that imports
this module picks up a change within seconds without a redeploy. Writes
(`update_provider` / `delete_provider` / `set_default_model`) write through to the backing
store *and* update the cache + env var for immediate local effect.

> **Cross-service note:** Cloud Run/Functions resolve `secret_key_ref` env vars at instance
> cold-start, not per call. Because this module fetches keys/model from the backing store on
> each (cached) access rather than relying on those bound env vars, changes propagate to
> already-warm instances of every service that imports it (the dashboard and the Cloud
> Functions both do). The remaining gap is administrative, not infrastructural: no dashboard
> endpoints call the write APIs yet — see the TODO in `dashboard/README.md`.

## Public API

* Supported providers
    ```python
    class LLMProvider(StrEnum):
        OPENAI = "openai"
        ANTHROPIC = "anthropic"
        GEMINI = "gemini"
    ```
    Each provider knows its API-key env var, its Secret Manager secret id, and the
    model-string prefixes (litellm convention) that select it.

* Get configured providers
    ```python
    def get_configured_providers() -> list[LLMProvider]:
    ```
    Returns the providers that currently have a non-blank API key.

* Update provider
    ```python
    def update_provider(provider: LLMProvider | str, api_key: str) -> None:
    ```
    Sets the API key for that provider as an env variable (immediate local effect) and
    writes it to GCP Secret Manager so other services pick it up within the cache TTL.

* Delete provider
    ```python
    def delete_provider(provider: LLMProvider | str) -> None:
    ```
    Clears the env variable and writes a blank version to the GCP secret.

* Get default model
    ```python
    def get_default_model() -> str:
    ```
    Returns the default model from the Firestore `config/llm` doc, falling back to the
    `LLM_MODEL_DEFAULT` env var (optional; not provisioned by Terraform — Firestore is
    the source of truth, so a fresh deploy needs one `set_default_model()` call).

* Set default model
    ```python
    def set_default_model(model: str) -> None:
    ```
    Sets the env var and updates the Firestore `config/llm` doc.

* Complete
    ```python
    def complete(
        provider: LLMProvider | str | None,
        model: str | None,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 4096,
        temperature: float = 0.0,
        output_type: type[T] | None = None,
    ) -> str | T:
    ```
    If `model` is `None`, the default model is used. If `provider` is `None`, it is
    inferred from the model-string prefix. If `output_type` is given, the response is
    parsed into that Pydantic model via litellm's structured-output response format;
    otherwise the assistant text is returned.

## Configuration

| Env var | Purpose |
|---|---|
| `LLM_MODEL_DEFAULT` | optional fallback default model when the Firestore `config/llm` doc is absent or unreadable; not provisioned by Terraform (Firestore is the source of truth) |
| `LLM_MAX_RETRIES` | `3` — litellm retries on transient provider failures |
| `GCP_PROJECT_ID` | when set, keys/models are read from & written to Secret Manager / Firestore; when unset, the module runs in env-only mode (local dev/tests) |

The provider is selected by the model string prefix (litellm convention):

| Prefix / example | Provider | API key env var | Secret id |
|---|---|---|---|
| `gpt-4o`, `gpt-4o-mini` | OpenAI | `OPENAI_API_KEY` | `openai-api-key` |
| `claude-3-5-sonnet-20241022` | Anthropic | `ANTHROPIC_API_KEY` | `anthropic-api-key` |
| `gemini/gemini-2.0-flash` | Google Gemini | `GEMINI_API_KEY` | `gemini-api-key` |

litellm receives the resolved `api_key` explicitly on each call (no global litellm state),
so a key changed via `update_provider` takes effect on the very next completion.

## Infra

`update_provider` / `delete_provider` / `set_default_model` write to GCP Secret Manager
and Firestore, so the service they run in needs:
- `roles/secretmanager.secretVersionAdder` on the per-provider secrets (scoped, not project-wide),
- Firestore write access.

Reads need `roles/secretmanager.secretAccessor`. See `infra/secrets.tf` and `infra/cloud_run.tf`.

## Boundaries

- **Depends on**: no other applybot component (talks to Firestore / Secret Manager directly
  via `GCP_PROJECT_ID`, mirroring the `models` leaf pattern — does not import `models`)
- **No knowledge of domain models** — this is a generic LLM utility
