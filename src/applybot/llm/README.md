# LLM

Provider-agnostic LLM client backed by [litellm](https://github.com/BerriAI/litellm).
litellm exposes a single `completion` API across providers (OpenAI, Anthropic,
Google Gemini, …), so swapping the underlying model is a config change, not a
code change — no vendor lock-in.

## Files

- **config.py** — `LLMSettings` (env-sourced model + retry settings)
- **client.py** — `LLMClient` and the `get_llm()` lazy singleton accessor

## Public API

```python
from applybot.llm.client import get_llm

# Simple text completion (uses the fast model by default)
response: str = get_llm().complete(prompt, system="...", temperature=0.7)

# Use the smarter model for complex reasoning
response: str = get_llm().complete(prompt, system="...", tier="smart")

# Structured output parsed to a Pydantic model
result: MyModel = get_llm().structured_output(prompt, output_type=MyModel, system="...", tier="smart")
```

Callers select model quality via the `tier` keyword argument (`"fast"` or
`"smart"`, default `"fast"`). Each tier resolves to a configured litellm model
string — consumers never reference model strings directly.

## Configuration

All settings use the `LLM_` env prefix:

| Env var | Default | Purpose |
|---|---|---|
| `LLM_MODEL_FAST` | `gpt-4o-mini` | litellm model string for `tier="fast"` |
| `LLM_MODEL_SMART` | `gpt-4o` | litellm model string for `tier="smart"` |
| `LLM_MAX_RETRIES` | `3` | litellm retries on transient provider failures |

The **provider** is selected by the model string prefix (litellm convention):

| Prefix / example | Provider | API key env var |
|---|---|---|
| `gpt-4o`, `gpt-4o-mini` | OpenAI | `OPENAI_API_KEY` |
| `claude-3-5-sonnet-20241022` | Anthropic | `ANTHROPIC_API_KEY` |
| `gemini/gemini-2.0-flash` | Google Gemini | `GEMINI_API_KEY` |

litellm reads each provider's API key from its standard environment variable
automatically — set the one(s) for the provider(s) you use.

### Example

```bash
# OpenAI
LLM_MODEL_FAST=gpt-4o-mini
LLM_MODEL_SMART=gpt-4o
OPENAI_API_KEY=sk-...

# Or Anthropic
LLM_MODEL_FAST=claude-3-5-haiku-20241022
LLM_MODEL_SMART=claude-3-5-sonnet-20241022
ANTHROPIC_API_KEY=sk-ant-...
```

## Boundaries

- **Depends on**: `litellm`, `config.py` (env-sourced settings)
- **No knowledge of domain models** — this is a generic LLM utility
- **Used by**: Query Builder, Ranker, Resume Tailor, Question Answerer, profile enrichment
