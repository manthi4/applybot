# ApplyBot — Project Status

> See [README.md](README.md) for project overview, architecture, tech stack, and setup instructions.

**Last updated:** June 2025

---

## ✅ What's Working

All modules are **implemented and importable**. No LLM-calling code has been tested against real APIs yet.

| Component | Notes |
|---|---|
| Config | Pydantic Settings, env-based |
| Models | Pydantic models + Firestore CRUD — Job, Application, UserProfile |
| LLM Client | Anthropic SDK wrapper — `complete()`, `structured_output()`, `with_tools()` |
| Profile | CRUD + JSON import/export |
| Resume | .docx parse → ResumeData → generate tailored .docx |
| Discovery scrapers | SerpAPI, Greenhouse, Lever, EuRemoteJobs — written against docs, untested live |
| Query Builder | LLM-powered search query generation |
| Deduplicator | rapidfuzz fuzzy matching + URL normalization |
| Relevance Ranker | Claude batch-scoring (0-100) |
| Discovery Orchestrator | Full pipeline: scrapers → dedup → rank → save |
| Resume Tailor | Claude rephrases/reorders per job (honesty guardrail) |
| Question Answerer | Claude drafts answers + cover letters, flags profile gaps |
| Application Preparer | Orchestrates tailor + answers + cover letter → Application record |
| Tracker | State machine with validated transitions |
| Gmail Integration | Email scanning + Claude classification → status updates |
| FastHTML Frontend | Overview, Job Queue, Applications, Profile pages (PicoCSS + HTMX) + TOTP session auth |
| CLI | `init-db`, `serve`, `bootstrap-profile`, `run-discovery` commands via Click |
| Deployment | Dockerfile, Terraform (GCP Cloud Run + Firestore + Cloud Functions + Cloud Scheduler + Artifact Registry + Secrets), health check |

### Tests — 23/23 passing

- `tests/test_models.py` — 10 tests (Job, UserProfile, Application CRUD against mock Firestore)
- `tests/test_discovery.py` — 9 tests (deduplicator, URL normalization)
- `tests/test_tracking.py` — 4 tests (state machine transitions, queries, summary)

### Recent Changes

- **Firestore migration** — Replaced SQLAlchemy + SQLite + Alembic with Google Cloud Firestore. All models are now Pydantic BaseModels with standalone CRUD functions. IDs changed from `int` to `str`. Removed alembic/ directory and alembic.ini.
- **Terraform updated** — Added Firestore database resource + composite indexes. Removed Cloud SQL and GCS data bucket volume mount. Updated IAM for `roles/datastore.user`.
- **Tests updated** — Mock Firestore client via `sys.modules` injection (enables testing without `google-cloud-firestore` installed, which is needed for Windows ARM64 where grpcio has no binary wheels).

---

## ❌ Not Yet Done

### MVP blockers

1. **End-to-end integration test** — No LLM-calling code tested with real API keys.
2. **Live scraper testing** — All scrapers written against docs only. EuRemoteJobs CSS selectors likely need tuning.
3. **Company target lists** — Greenhouse/Lever scrapers need curated robotics/ML company slugs.
4. **Google OAuth flow** — Gmail integration needs OAuth2 setup script for user consent.

### Robustness

5. **Error handling & retries** — LLM calls can fail or return malformed JSON.
6. **More test coverage** — No tests for: scrapers (mock HTTP), ranker (mock LLM), resume parsing, API endpoints.
7. **Cost tracking** — No visibility into LLM API costs per run.

### Future

8. Workday scraper
9. Auto-submission (form filling)
10. Firestore composite index tuning based on real query patterns

---

## Next Steps (priority order)

1. Deploy to GCP and verify Firestore connectivity
2. Set up `.env` with API keys (Anthropic, SerpAPI)
3. Test discovery pipeline end-to-end with live APIs
4. Curate company target lists for Greenhouse/Lever
5. Test application preparation on a real job
6. Add mock-based tests for scrapers, ranker, API endpoints
