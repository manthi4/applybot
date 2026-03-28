# LLM

Thin wrapper around the Anthropic Vertex AI SDK for all Claude API interactions. Provides three call patterns and a module-level singleton.

## Files

- **client.py** — `LLMClient` class and `llm` singleton instance

## Public API

```python
from applybot.llm.client import llm

# Simple text completion
response: str = llm.complete(prompt, system="...", temperature=0.7)

# Structured output parsed to a Pydantic model
result: MyModel = llm.structured_output(prompt, output_type=MyModel, system="...")

# Tool-use call (returns full Anthropic Message for tool call inspection)
message: anthropic.types.Message = llm.with_tools(prompt, tools=[...], system="...")
```

### Configuration

- Model selection via `settings.vertex_model_fast` / `settings.vertex_model_smart`
- Pass `model=` to any method to override
- Authentication via Google Application Default Credentials (ADC) — no API key needed
- GCP project from `settings.gcp_project_id`
- Vertex region from `settings.vertex_region` (default: `us-east5`)
- Max retries: `settings.vertex_max_retries`

## Boundaries

- **Depends on**: `config.py` (for GCP project, region, and model settings)
- **No knowledge of domain models** — this is a generic LLM utility
- **Used by**: Query Builder, Ranker, Resume Tailor, Question Answerer, Gmail classifier
- Consumers are responsible for prompt engineering and output parsing (except `structured_output` which handles JSON extraction)
