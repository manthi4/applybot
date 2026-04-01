# LLM

Multi-provider LLM wrapper supporting Google Gemini and Anthropic Claude. Provides three call patterns and a module-level singleton.

## Files

- **client.py** — `LLMClient` abstract base class, `GeminiClient`, `AnthropicClient`, and `get_llm()` lazy singleton accessor

## Public API

```python
from applybot.llm.client import get_llm

# Simple text completion (uses the fast model by default)
response: str = get_llm().complete(prompt, system="...", temperature=0.7)

# Use the smarter model for complex reasoning
response: str = get_llm().complete(prompt, system="...", tier="smart")

# Structured output parsed to a Pydantic model
result: MyModel = get_llm().structured_output(prompt, output_type=MyModel, system="...", tier="smart")

# Tool-use call — AnthropicClient only
message = get_llm().with_tools(prompt, tools=[...], system="...")
```

### Configuration

The active backend is set by `settings.llm_provider` (env var `LLM_PROVIDER`):

| Provider | Value | Auth |
|---|---|---|
| Google Gemini (default) | `"gemini"` | Google ADC (service account) |
| Anthropic Claude on Vertex | `"anthropic"` | Google ADC (service account) |

Callers select model quality via the `tier` keyword argument (`"fast"` or `"smart"`, default `"fast"`). Each provider resolves the tier to its own configured model name — consumers never reference model strings directly.

**Gemini settings** (env vars):
- `LLM_PROVIDER=gemini` (default)
- `GCP_PROJECT_ID`, `VERTEX_REGION` — Google Cloud project and Vertex AI region
- `GEMINI_MODEL_FAST` — default `gemini-2.0-flash`
- `GEMINI_MODEL_SMART` — default `gemini-2.5-pro`
- Uses the `google-genai` SDK (`google-genai>=1.0.0`) with Vertex AI

**Anthropic/Claude settings** (env vars):
- `LLM_PROVIDER=anthropic`
- `GCP_PROJECT_ID`, `VERTEX_REGION` — Google Cloud project and Vertex AI region
- `ANTHROPIC_MODEL_FAST`, `ANTHROPIC_MODEL_SMART` — default `claude-sonnet-4-6`
- `ANTHROPIC_MAX_RETRIES` — default `3`

Pass `model=` to any method to override the default model for that call.

## Boundaries

- **Depends on**: `config.py` (for provider selection and model settings)
- **No knowledge of domain models** — this is a generic LLM utility
- **Used by**: Query Builder, Ranker, Resume Tailor, Question Answerer, Gmail classifier
- `with_tools()` is only available with the `"anthropic"` provider
