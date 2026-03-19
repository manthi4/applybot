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
| **serpapi.py** | LinkedIn, Indeed, Glassdoor | SerpAPI Google Jobs endpoint |
| **greenhouse.py** | Greenhouse boards | Public API (`boards-api.greenhouse.io`) |
| **lever.py** | Lever postings | Public API (`api.lever.co`) |
| **euremotejobs.py** | EuRemoteJobs | HTML scraping with lxml |

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

## Boundaries

- **Depends on**: `models` (Job ORM, JobStatus, JobSource), `llm` (query building, ranking), `profile` (user profile for queries and ranking), `config` (API keys, thresholds)
- **Does not depend on**: Application, Tracking, or Dashboard
- **Used by**: CLI/scheduler entry points, Dashboard (via DB)
- Scrapers are isolated from each other — one scraper failing doesn't block others
- The orchestrator is the only component that writes to the database; individual scrapers return `RawJob` dataclasses
- Greenhouse/Lever scrapers require curated company slug lists (currently empty — needs population)
