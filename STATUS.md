# ApplyBot — Project Status & Plan

## What Is This?

An AI-powered system to automate job applications. It discovers ML/robotics jobs daily, prepares tailored resumes and answers, and presents them for human review before submission.

**Tech stack:** Python 3.12, Anthropic Claude SDK, SQLAlchemy + SQLite (dev) / PostgreSQL (prod), FastAPI, Streamlit, SerpAPI, python-docx, GCP Cloud Functions

---

## Current State (March 19, 2026)

### ✅ Implemented — Code Written, importable

| Module | Files | Status |
|---|---|---|
| **Config** | `src/applybot/config.py` | Done. Pydantic Settings, env-based config. |
| **Models** | `src/applybot/models/` (base, job, profile, application) | Done. SQLAlchemy ORM with SQLite for dev. All 16 model tests pass. |
| **LLM Client** | `src/applybot/llm/client.py` | Done. Anthropic SDK wrapper with `complete()`, `structured_output()`, `with_tools()`. |
| **Profile Manager** | `src/applybot/profile/manager.py` | Done. CRUD, JSON import/export. |
| **Resume Manager** | `src/applybot/profile/resume.py` | Done. Parse .docx → ResumeData, generate tailored .docx. |
| **Scraper Base** | `src/applybot/discovery/scrapers/base.py` | Done. `BaseScraper` ABC + `RawJob` dataclass. |
| **SerpAPI Scraper** | `src/applybot/discovery/scrapers/serpapi.py` | Done. Google Jobs API, pagination, date parsing. |
| **Greenhouse Scraper** | `src/applybot/discovery/scrapers/greenhouse.py` | Done. Public boards API, query filtering. |
| **Lever Scraper** | `src/applybot/discovery/scrapers/lever.py` | Done. Public postings API, query filtering. |
| **EuRemoteJobs Scraper** | `src/applybot/discovery/scrapers/euremotejobs.py` | Done. HTML scraping with lxml. |
| **Query Builder** | `src/applybot/discovery/query_builder.py` | Done. LLM-powered search query generation from profile. |
| **Deduplicator** | `src/applybot/discovery/deduplicator.py` | Done. Fuzzy matching (rapidfuzz) + URL normalization. 9 tests pass. |
| **Relevance Ranker** | `src/applybot/discovery/ranker.py` | Done. Claude batch-scores jobs against profile (0-100). |
| **Discovery Orchestrator** | `src/applybot/discovery/orchestrator.py` | Done. Runs scrapers → dedup → rank → save to DB. |
| **Resume Tailor** | `src/applybot/application/resume_tailor.py` | Done. Claude rephrases/reorders resume content per job (honesty guardrail). |
| **Question Answerer** | `src/applybot/application/question_answerer.py` | Done. Claude drafts answers + cover letters, flags profile gaps. |
| **Application Preparer** | `src/applybot/application/preparer.py` | Done. Orchestrates tailor + answers + cover letter → Application record. |
| **Tracker** | `src/applybot/tracking/tracker.py` | Done. State machine with validated transitions. 13 tests pass. |
| **Gmail Integration** | `src/applybot/tracking/gmail.py` | Done. Email scanning + Claude classification → status updates. |
| **FastAPI Backend** | `src/applybot/dashboard/api.py` | Done. REST endpoints for jobs, applications, profile, dashboard summary. |
| **Streamlit Frontend** | `src/applybot/dashboard/frontend.py` | Done. Overview, Job Queue, Applications, Profile pages. |

### ✅ Tests — 29/29 passing

- `tests/test_models.py` — 7 tests (Job, UserProfile, Application CRUD)
- `tests/test_discovery.py` — 9 tests (deduplicator, URL normalization)
- `tests/test_tracking.py` — 13 tests (state machine transitions, queries, summary)

### ✅ Infrastructure

- `pyproject.toml` — project config with deps
- `alembic/` — database migration setup
- `.pre-commit-config.yaml` — black, ruff, mypy hooks
- `.env.example` — environment variable template
- SQLite database initialized at `data/applybot.db`

---

## ❌ Not Yet Done — Needs Work Before Usable

### Must-do to reach MVP

1. **End-to-end integration test** — Run the full pipeline (discovery → prepare → review) manually with real API keys to catch integration issues. None of the LLM-calling code has been tested with a real API yet.

2. **Scraper testing against live APIs** — The SerpAPI, Greenhouse, Lever, and EuRemoteJobs scrapers were written against docs but haven't been tested against real responses. CSS selectors for EuRemoteJobs likely need tuning.

3. **Profile bootstrap flow** — There's no CLI or entrypoint to: (a) import your existing resume .docx, (b) run the profile extraction agent, (c) fill in gaps interactively. This is critical since everything depends on the profile.

4. **Company target lists** — Greenhouse/Lever scrapers need a curated list of robotics/ML company slugs. Currently empty lists.

5. **Entrypoints / CLI** — No way to actually *run* anything yet. Need:
   - `python -m applybot.cli discover` — run discovery
   - `python -m applybot.cli prepare` — prepare applications
   - `python -m applybot.cli serve` — start FastAPI + optionally Streamlit

6. **Google OAuth flow** — Gmail integration requires OAuth2 user consent flow to get tokens. Need a setup script for this.

### Should-do for robustness

7. **Error handling & retries** — LLM calls can fail or return malformed JSON. Need better fallback behavior.

8. **More test coverage** — No tests yet for: scrapers (mock HTTP), ranker (mock LLM), resume parsing, API endpoints.

9. **Alembic migrations** — Currently using `init_db()` which creates tables directly. Should generate proper Alembic migration files for production.

10. **Cost tracking** — No visibility into LLM API costs per run.

### Future phases (not started)

11. **GCP deployment** — Cloud Functions, Cloud Scheduler, Cloud Run for dashboard.
12. **Workday scraper** — Complex, per-company tenants. Deferred.
13. **Auto-submission** — Actually filling and submitting application forms. Deferred.

---

## Project Structure

```
applybot/
├── pyproject.toml
├── alembic.ini
├── alembic/env.py
├── .env.example
├── .pre-commit-config.yaml
├── core_idea.md
├── data/                          # Local data (resume, DB, exports)
│   └── applybot.db
├── src/applybot/
│   ├── config.py                  # Pydantic Settings
│   ├── models/
│   │   ├── base.py                # SQLAlchemy engine, session, Base
│   │   ├── job.py                 # Job, JobStatus, JobSource
│   │   ├── profile.py             # UserProfile
│   │   └── application.py         # Application, ApplicationStatusUpdate
│   ├── llm/
│   │   └── client.py              # Anthropic SDK wrapper
│   ├── profile/
│   │   ├── manager.py             # Profile CRUD, JSON import/export
│   │   └── resume.py              # .docx parse/generate
│   ├── discovery/
│   │   ├── scrapers/
│   │   │   ├── base.py            # BaseScraper ABC, RawJob
│   │   │   ├── serpapi.py         # SerpAPI (LinkedIn + Indeed)
│   │   │   ├── greenhouse.py      # Greenhouse boards API
│   │   │   ├── lever.py           # Lever postings API
│   │   │   └── euremotejobs.py    # Custom HTML scraper
│   │   ├── query_builder.py       # LLM generates search queries
│   │   ├── deduplicator.py        # Fuzzy dedup (rapidfuzz)
│   │   ├── ranker.py              # LLM relevance scoring
│   │   └── orchestrator.py        # Full discovery pipeline
│   ├── application/
│   │   ├── resume_tailor.py       # LLM resume customization
│   │   ├── question_answerer.py   # LLM Q&A + cover letter
│   │   └── preparer.py            # Orchestrates full app prep
│   ├── tracking/
│   │   ├── tracker.py             # State machine + queries
│   │   └── gmail.py               # Gmail API email scanning
│   └── dashboard/
│       ├── api.py                 # FastAPI REST endpoints
│       └── frontend.py            # Streamlit web UI
└── tests/
    ├── test_models.py             # 7 tests
    ├── test_discovery.py          # 9 tests
    └── test_tracking.py           # 13 tests
```

---

## Key Decisions Made

| Decision | Rationale |
|---|---|
| SQLite for dev, PostgreSQL for prod | Avoids needing a DB server locally. Easy swap via `DATABASE_URL`. |
| Lazy engine creation | Models import without DB connection |
| Direct Anthropic SDK (no LangChain) | Simpler, fewer deps, more debuggable |
| Human-in-the-loop | Agent never submits without explicit approval |
| Resume honesty guardrail | Tailoring agent can only rephrase/reorder, not fabricate |
| SerpAPI for LinkedIn/Indeed | Reliable aggregator API, avoids anti-bot issues |
| Streamlit for dashboard MVP | Fast to build, Python-native, can swap later |

---

## Recommended Next Steps (in priority order)

1. **Create CLI entrypoints** — so you can actually run things
2. **Set up `.env` with your API keys** (Anthropic, SerpAPI)
3. **Import your resume** and bootstrap the profile
4. **Test discovery pipeline** end-to-end with live APIs
5. **Curate company target lists** for Greenhouse/Lever
6. **Test application preparation** on a real job
7. **Add mock-based tests** for scrapers, ranker, and API endpoints
8. **Deploy to GCP**
