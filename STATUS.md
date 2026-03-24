# ApplyBot — Project Status

> See [README.md](README.md) for project overview, architecture, tech stack, and setup instructions.

**Last updated:** March 24, 2026

---

## ✅ What's Working

All modules are **implemented and importable**. No LLM-calling code has been tested against real APIs yet.

| Component | Notes |
|---|---|
| Config | Pydantic Settings, env-based |
| Models | SQLAlchemy ORM — Job, Application, UserProfile |
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
| FastAPI Backend | REST endpoints for jobs, applications, profile, summary |
| FastHTML Frontend | Overview, Job Queue, Applications, Profile pages (PicoCSS + HTMX) |
| CLI | `init-db`, `serve`, `bootstrap-profile`, `run-discovery` commands via Click |
| Alembic Migrations | Initial migration created and stamped |
| Deployment | Dockerfile, Terraform (GCP Cloud Run + Cloud SQL + Cloud Functions + Cloud Scheduler + Artifact Registry + Secrets), health check |

### Tests — 29/29 passing

- `tests/test_models.py` — 7 tests (Job, UserProfile, Application CRUD)
- `tests/test_discovery.py` — 9 tests (deduplicator, URL normalization)
- `tests/test_tracking.py` — 13 tests (state machine transitions, queries, summary)

---

## ❌ Not Yet Done

### MVP blockers

1. **CLI entrypoints** — ✅ Done. `init-db`, `serve`, `bootstrap-profile` commands.
2. **Profile bootstrap flow** — ✅ Done. `applybot bootstrap-profile resume.docx` parses and stores profile.
3. **End-to-end integration test** — No LLM-calling code tested with real API keys.
4. **Live scraper testing** — All scrapers written against docs only. EuRemoteJobs CSS selectors likely need tuning.
5. **Company target lists** — Greenhouse/Lever scrapers need curated robotics/ML company slugs.
6. **Google OAuth flow** — Gmail integration needs OAuth2 setup script for user consent.

### Robustness

7. **Error handling & retries** — LLM calls can fail or return malformed JSON.
8. **More test coverage** — No tests for: scrapers (mock HTTP), ranker (mock LLM), resume parsing, API endpoints.
9. **Alembic migrations** — ✅ Done. Initial migration created.
10. **Cost tracking** — No visibility into LLM API costs per run.

### Future

11. GCP deployment — ✅ Terraform config created. See DEPLOY.md for setup instructions. Cloud Functions Gen 2 + Cloud Scheduler for automated daily discovery runs configured.
12. Workday scraper
13. Auto-submission (form filling)

---

## Next Steps (priority order)

1. Set up `.env` with API keys (Anthropic, SerpAPI)
2. Test discovery pipeline end-to-end with live APIs
3. Curate company target lists for Greenhouse/Lever
4. Test application preparation on a real job
5. Add mock-based tests for scrapers, ranker, API endpoints
6. Deploy to GCP
