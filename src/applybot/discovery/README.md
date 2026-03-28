# Discovery

Automated job search pipeline: generates queries from the user profile, scrapes multiple job boards in parallel, deduplicates results, ranks by relevance using Claude, and saves new jobs to the database.

## Files

- **orchestrator.py** — `run_discovery()` — top-level pipeline entry point
- **query_builder.py** — `build_search_queries()` — LLM-powered query generation
- **deduplicator.py** — `deduplicate()` — fuzzy matching + URL normalization
- **ranker.py** — `rank_jobs()` — Claude batch-scoring (0-100)
- **scrapers/** — pluggable scraper implementations

### Scrapers

| File | Source | Method |
|---|---|---|
| **base.py** | — | `BaseScraper` ABC + `RawJob` dataclass |
| **serpapi.py** | LinkedIn, Indeed, Glassdoor | SerpAPI Google Jobs endpoint (requires `SERPAPI_KEY`) |
| **greenhouse.py** | Greenhouse boards | Public API (`boards-api.greenhouse.io`) — no key needed |
| **lever.py** | Lever postings | Public API (`api.lever.co`) — no key needed |
| **euremotejobs.py** | EuRemoteJobs | HTML scraping with lxml |

#### Greenhouse & Lever: Company Watchlists

Greenhouse and Lever don't offer cross-company search — their APIs are per-company boards only. The scrapers pull all jobs from a curated list of companies and filter by keyword relevance locally. SerpAPI handles broad keyword discovery across all companies/sources.

Default company lists are defined in `orchestrator.py` (`DEFAULT_GREENHOUSE_COMPANIES`, `DEFAULT_LEVER_COMPANIES`) and should be edited to match the companies you want to track.

**Default Greenhouse companies** (`boards.greenhouse.io/<slug>`):

| Slug | Company |
|---|---|
| `openai` | OpenAI |
| `waymo` | Waymo |
| `covariant` | Covariant |
| `nuro` | Nuro |
| `zoox` | Zoox |
| `imbue` | Imbue |
| `shield-ai` | Shield AI |
| `robust-robotics` | Robust Robotics |
| `applovin` | AppLovin |
| `scale` | Scale AI |

**Default Lever companies** (`jobs.lever.co/<slug>`):

| Slug | Company |
|---|---|
| `anduril` | Anduril Industries |
| `scale-ai` | Scale AI |
| `boston-dynamics` | Boston Dynamics |
| `figureai` | Figure AI |
| `skydio` | Skydio |
| `physical-intelligence` | Physical Intelligence |
| `apptronik` | Apptronik |
| `innerspace` | InnerSpace |
| `cohere` | Cohere |
| `mistral` | Mistral AI |

## Public API

### Pipeline Entry Point

```python
from applybot.discovery.orchestrator import run_discovery

result: DiscoveryResult = await run_discovery(
    scrapers=[serpapi, greenhouse, lever],
    location="Remote",
    max_results=100,
)
# DiscoveryResult: total_scraped, after_dedup, above_threshold, new_jobs_saved, top_matches
```

### Scraper Interface

All scrapers implement `BaseScraper`:

```python
class BaseScraper(ABC):
    @property
    def source_name(self) -> str: ...

    async def search(self, queries: list[str], location: str, max_results: int) -> list[RawJob]: ...
```

### RawJob (scraper output schema)

```python
@dataclass
class RawJob:
    title: str
    company: str
    location: str
    description: str
    url: str
    source: str
    posted_date: date | None
    extra: dict[str, Any]
```

### Individual Components

```python
from applybot.discovery.query_builder import build_search_queries
queries: list[str] = build_search_queries(profile, max_queries=6)

from applybot.discovery.deduplicator import deduplicate
unique: list[RawJob] = deduplicate(jobs)

from applybot.discovery.ranker import rank_jobs
ranked: list[tuple[RawJob, int, str]] = rank_jobs(jobs, profile)
# Returns (job, score, reasoning) tuples, filtered by threshold
```

## Deployment

### Cloud Function (GCP)

Discovery runs as a **Cloud Functions Gen 2** HTTP function. It must be triggered manually — either via the CLI locally, or by sending an HTTP POST to the function URL in GCP.

- **Entry point**: `handle_discovery` in `main.py` (project root)
- **Runtime**: Python 3.12, 512Mi memory, 300s timeout
- **Terraform**: `infra/cloud_functions.tf`

To invoke the deployed function manually via `gcloud`:

```bash
gcloud functions call applybot-discovery --region=us-central1
```

### CLI (local)

```bash
applybot run-discovery
applybot run-discovery --location "Remote" --max-results 50
```

## Boundaries

- **Depends on**: `models` (Job, JobStatus, JobSource), `llm` (query building, ranking), `profile` (user profile for queries and ranking), `config` (API keys, thresholds)
- **Does not depend on**: Application, Tracking, or Dashboard
- **Used by**: CLI/scheduler entry points, Dashboard (via DB)
- Scrapers are isolated from each other — one scraper failing doesn't block others
- The orchestrator is the only component that writes to the database; individual scrapers return `RawJob` dataclasses
- Greenhouse/Lever scrapers require curated company slug lists (currently empty — needs population)

## Tests

Tests live in `src/applybot/discovery/tests/` alongside the component code.

Run only discovery tests:

```bash
pytest src/applybot/discovery/tests/ -v
```

| File | Covers |
|---|---|
| `conftest.py` | Shared fixtures (`make_raw_job`, `mock_profile`) |
| `test_deduplicator.py` | `deduplicate()`, `_normalize_url()`, `_build_key()` |
| `test_query_builder.py` | `build_search_queries()` — LLM mocking + fallback |
| `test_ranker.py` | `rank_jobs()`, `_score_batch()`, `_build_profile_summary()` |
| `test_scrapers.py` | `BaseScraper` ABC, SerpAPI, Greenhouse, Lever scrapers |
| `test_orchestrator.py` | `run_discovery()` pipeline, `_map_source()`, `_run_scraper()` |
