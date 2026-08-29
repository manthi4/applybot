# LLM

Provider-agnostic LLM client backed by [litellm](https://github.com/BerriAI/litellm),
so swapping the underlying model is a config change, not a code change — no vendor lock-in.

## Files
- **providers.py** — `LLMProvider` enum, per-provider metadata, and model-prefix routing (leaf: no runtime state, easy to extend)
- **_backends.py** — GCP Secret Manager write shims (new secret versions on key update/delete); reads happen via the platform volume mount, not the API
- **client.py** — the public API: mounted-file key lookup, Firestore-backed default-model store (TTL-cached), and `complete()` (no singleton, no `config.py`)

## Design: runtime-mutable config

> **Status:** target spec for the `sal/rework_llm_api_key_caching` rework (docs-first
> commit; code and Terraform changes follow on this branch). The PR description on that
> branch covers the migration plan and the stale-key bug in the previous design.

Provider API keys and the default model are **mutable while the app is deployed** (the
set of providers itself is a code edit in `providers.py`). There is deliberately no
`config.py` / settings object — these values change at runtime, so every value is read
fresh on each access.

- **API keys** live in **GCP Secret Manager** (one secret per provider) and are delivered
  to every runtime as **volume-mounted files** (`/etc/secrets/<secret_id>`, version
  `latest`). The platform refreshes mounted secret files automatically when a new version
  is added — no restart, no new revision — so a key rotated from the dashboard reaches all
  services within minutes. `client.py` re-reads the file on each completion (a small-file
  read costs microseconds), so there is **no key cache and no env-var write-back**.
- **Default model** lives in a **Firestore** document (`config/llm` → `default_model`)
  (CRUD via the `models` component) behind a short-TTL in-process cache. Model names are
  not secret, so Firestore — not Secret Manager — is the right store.

Writes (`update_provider` / `delete_provider` / `set_default_model`) write through to the
backing store *and* record an in-process override, so the writing process (the dashboard)
uses the new value immediately instead of waiting for the mount to refresh.

Key lookup order: in-process override → mounted file (`LLM_SECRETS_DIR`, default
`/etc/secrets`) → provider env var. The env var exists as the **local-dev/tests
fallback** (no mount on a laptop); it is not provisioned on GCP.

The remaining gap is administrative, not infrastructural: no dashboard endpoints call the
write APIs yet — see the TODO in `dashboard/README.md`.

## Public API

* Supported providers
    ```python
    class LLMProvider(StrEnum):
        OPENAI = "openai"
        ANTHROPIC = "anthropic"
        GEMINI = "gemini"
        GLM = "glm"
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
    def update_provider(provider: LLMProvider | str, api_key: str) -> None
    ```
    Adds a new GCP Secret Manager version for the provider's secret and records an
    in-process override (immediate effect in the writing process). Other services pick
    the new key up when the platform refreshes their volume mount (typically within
    minutes). Locally (no `GCP_PROJECT_ID`) it just sets the env-var fallback.

* Delete provider
    ```python
    def delete_provider(provider: LLMProvider | str) -> None
    ```
    Adds a blank secret version (mounts refresh to empty) and clears the in-process
    override / env-var fallback.

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
| `LLM_SECRETS_DIR` | `/etc/secrets` — directory where provider key secrets are volume-mounted; point it at a local dir in tests to exercise the mount path |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `GEMINI_API_KEY` / `ZAI_API_KEY` | local-dev/tests fallback when the mount is absent; not provisioned on GCP |
| `LLM_MODEL_DEFAULT` | optional fallback default model when the Firestore `config/llm` doc is absent or unreadable; not provisioned by Terraform (Firestore is the source of truth) |
| `LLM_MAX_RETRIES` | `3` — litellm retries on transient provider failures |
| `GCP_PROJECT_ID` | when set, key writes go to Secret Manager and the default model is read from/written to Firestore; when unset, the module runs in env-only mode (local dev/tests) |

The provider is selected by the model string prefix (litellm convention):

| Prefix / example | Provider | Local-dev env var | Secret id (= mount file name) |
|---|---|---|---|
| `gpt-4o`, `gpt-4o-mini` | OpenAI | `OPENAI_API_KEY` | `openai-api-key` |
| `claude-3-5-sonnet-20241022` | Anthropic | `ANTHROPIC_API_KEY` | `anthropic-api-key` |
| `gemini/gemini-2.0-flash` | Google Gemini | `GEMINI_API_KEY` | `gemini-api-key` |
| `zai/glm-5.2` | GLM (Z.AI) | `ZAI_API_KEY` | `glm-api-key` |

litellm receives the resolved `api_key` explicitly on each call (no global litellm state),
so a key changed via `update_provider` takes effect on the very next completion.

## Infra

Provider secrets are mounted (version `latest`) at `/etc/secrets/<secret_id>` in both the
Cloud Run service (`volumes` / `volume_mounts` in `infra/cloud_run.tf`) and the discovery
Cloud Function (`secret_volumes` in `infra/cloud_functions.tf`), so every runtime needs
`roles/secretmanager.secretAccessor` on the per-provider secrets (scoped, not
project-wide).

`update_provider` / `delete_provider` / `set_default_model` write to GCP Secret Manager
and Firestore, so the service they run in needs:
- `roles/secretmanager.secretVersionAdder` on the per-provider secrets (scoped, not project-wide),
- Firestore write access.

See `infra/secrets.tf`, `infra/cloud_run.tf`, `infra/cloud_functions.tf`.

## Boundaries

- **Depends on**: `models` (Firestore config CRUD via its config helpers); talks to
  GCP Secret Manager directly via `GCP_PROJECT_ID`; imports no other applybot component
- **No knowledge of domain models** — this is a generic LLM utility
