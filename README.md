# ApplyBot

A system to discover relevant jobs, prepare tailored applications, and track the application lifecycle. All as an observable, cloud hosted, modular system. Mostly python based, leveraging LLMs to help interpret job postings and generate tailored job application components.

---

## Documentation guide

The documentation for ApplyBot is meant to be hierarchical and LLM friendly. A top level README like this one should try to avoid delving into the implementation details of lower level components that it mentions. Instead it can talk about what those components are meant to do and define clear boundaries and APIs for them. Lower level README should touch on the more specific implementation details pertaining to their specific components.

## Overview

This section is meant to give an outline of each component in the applybot system, it should not contain too much implementation details. ApplyBot is organized with the following components:

1. **Discovery Function** — Searches multiple job boards using LLM-generated queries based on the user profile, deduplicates results with fuzzy matching, and uses an llm to rank jobs by relevance to your profile (0-100 score with reasoning). Then saves them into the database.
2. **Application Preperation Function** — For each approved job, tailors your resume, drafts answers to any present application questions, generates a cover letter, and flags any profile gaps that need human input. Creates an Application record for review.
3. **Database** - EVERY OTHER COMPONENT OF THIS APP IS STATELESS. The chosen database maintains and tracks the current state of the entire app.
    * **Profile** - Maintains a structured reference document of the user's skills, experiences, and interests. Essentially a structured representation of their resume with any additional information they provide.
    * **Job Postings** - Stores all discovered job postings (see [Models](src/applybot/models/README.md) for the `Job` schema).
    * **Applications** - Stores all applications created by the preparation function, each linked to a job posting by its Firestore document ID.
        * Applications carry a `status` field: `ready_for_review`, `approved`, `submitted`, `received`, `interview`, `offer`, `rejected`, or `withdrawn` (see `ApplicationStatus` in `models/application.py`).
4. **Dashboard** — Web UI for reviewing and approving discoverd jobs, managing applications, editing profile, and viewing pipeline statistics.

5. **LLM Engine** - Provider-agnostic LLM client backed by litellm, exposing a consistent API (text completion + structured output) to the rest of the components. The provider is chosen by the model-string prefix (`gpt-*`, `claude-*`, `gemini/*`, `zai/*`); provider API keys (Secret Manager) and the default model (Firestore) are mutable at runtime — no redeploy to swap models or rotate keys.

**Human-in-the-loop**: The agent prepares everything, but never submits without explicit approval. Safety guardrail: the agent never submits without explicit approval.

---

## Project Structure

```
applybot/
├── README.md               # This file
├── AGENTS.md               # Build/test/style conventions
├── DEPLOY.md               # Full deployment guide (manual + CI/CD)
├── pyproject.toml          # Dependencies and tool config (black, ruff, mypy)
├── requirements.txt        # Cloud Function deploy manifest (functions-framework + the package)
├── data/                   # Local data (resume, exports)
├── .github/workflows/
│   ├── terraform.yml       # Terraform plan/apply CI workflow
│   └── docker.yml          # Docker build & push CI workflow
├── infra/                  # Terraform IaC (Cloud Run, Cloud Functions, Firestore, GCS, secrets)
├── src/applybot/
│   ├── application/        # Resume parsing/generation, tailoring, Q&A, cover letters
│   ├── dashboard/          # FastHTML web UI (pages/, services/, components/, theme)
│   ├── discovery/          # Job discovery pipeline + scrapers/ + Cloud Function entry point
│   ├── llm/                # LLM client — litellm-backed, provider-agnostic (providers, _backends, client)
│   ├── models/             # Pydantic models + Firestore CRUD (Job, Application, UserProfile)
│   ├── cli.py              # `applybot` CLI (serve, setup-auth)
│   └── storage.py          # GCS storage layer for file storage (resumes, etc.)
└── tests/                  # Integration test suite
```

Each component directory may carry its own `requirements.in` / `requirements-dev.in` that mirror the root `pyproject.toml`. The root `requirements.txt` is a minimal deploy manifest for the Cloud Functions (functions-framework plus the installed package), not a compiled lockfile.

---

## Testing

The top level tests/ repo is intended for integration tests involving multiple components. More specific component level testing is handled inside more specific component level testing folders. It is important to keep tests updated when changing any functionality.


## Cross-Cutting Dependencies

- **LLM Engine** — Used by: Discovery Function, Application Preperation Function, Dashboard
- **Models** — Shared Firestore data layer accessed by all components

---

## [Data Models](src/applybot/models/README.md)

## CI/CD (GitHub Actions)

Two workflows in `.github/workflows/` automate infrastructure and image deployment:

| Workflow | File | Triggers | What it does |
|---|---|---|---|
| **Terraform** | `terraform.yml` | Manual dispatch (plan/apply) or push to `main` with `--tf-apply` in commit message | Authenticates to GCP, runs `terraform init` → `plan` → `apply` in `infra/` |
| **Docker** | `docker.yml` | Manual dispatch (optional `image_tag`) or push to `main` with `--docker` in commit message | Builds Docker image, tags with version + `latest`, pushes to Artifact Registry |

Both workflows authenticate via a GCP service account key stored in GitHub Secrets and use a concurrency group to prevent parallel runs.

**Quick usage:**

```bash
# Terraform
gh workflow run terraform.yml                    # plan + apply
gh workflow run terraform.yml -f action=plan     # plan only

# Docker
gh workflow run docker.yml                       # tag = short SHA
gh workflow run docker.yml -f image_tag=v2       # custom tag

# Commit-message triggers (push to main)
git commit -m "update infra --tf-apply"
git commit -m "fix bug --docker"
```

**Required GitHub Secrets:** `GCP_SA_KEY`, `GCP_PROJECT_ID`, `TF_VAR_SERPAPI_KEY`.
**Optional GitHub Variables:** `GCP_REGION` (default: `us-central1`), `IMAGE_TAG` (default: `latest`).

See [DEPLOY.md](DEPLOY.md) § "CI/CD with GitHub Actions" for full setup instructions (GCS bucket for Terraform state, CI service account creation, secrets configuration).


## Configuration

Pydantic Settings, loading from a `.env` file. See [.env.example](.env.local) for examples

---

## Setup

```bash
# Install (with dev tools and dashboard)
pip install -e ".[dev]"

# Initialize database
python -c "from applybot.models.base import init_db; init_db()"

# Run tests
pytest
```

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| Provider-agnostic LLM via litellm (no LangChain) | Swap providers by changing the model string; API keys and default model are runtime-mutable (Secret Manager + Firestore), no vendor lock-in |
| Firestore (serverless NoSQL) | No DB server to manage or pay for; generous free tier, scales automatically |
| Human-in-the-loop | Agent never submits without explicit approval |
| Resume honesty guardrail | Tailoring can only rephrase/reorder, not fabricate |
| SerpAPI for LinkedIn/Indeed | Reliable aggregator API, avoids anti-bot issues |
| Free APIs for Greenhouse/Lever | Public boards APIs, no auth needed |
| FastHTML for dashboard | Lightweight, Python-native, HTMX-powered, no pyarrow/heavy deps |
| Lazy client creation | Models import without requiring a DB connection |
| Async scraper execution | All scrapers run in parallel; one failing doesn't block others |
| Batch LLM ranking | Jobs sent in groups of 5 to reduce API calls and costs |

---

## Deployment

ApplyBot is hosted on **Google Cloud Platform** in a single GCP project (ID configured at deploy time via Terraform). The default region is `us-central1`.

### Compute Services

| Service | GCP Product | What it runs | Entry point |
|---|---|---|---|
| **Dashboard** | Cloud Run | FastHTML web UI on port 8000 | Docker image from Artifact Registry |
| **Discovery Pipeline** | Cloud Functions (Gen 2) | Job scraping + dedup + ranking | `handle_discovery` in `src/applybot/discovery/main.py` |
| **Application Preparer** | Cloud Functions (Gen 2) — *not yet deployed in infra* | Resume tailoring + Q&A + cover letters | Triggered by dashboard over HTTP (`APPLICATION_PREPARER_FUNCTION_URL`) |

The dashboard scales 0–1 (serverless, pay-per-use). Discovery runs on a Cloud Scheduler cron and can also be triggered manually via the **"Run Discovery Now"** button on the dashboard Overview page. Application preparation is triggered manually via the **"Build Approved Applications"** button on the dashboard Job Queue page, which calls the preparer Cloud Function over HTTP.


---

## Cost Considerations

- **SerpAPI**: ~$50/month for 5,000 searches
- **LLM calls (OpenAI / Anthropic / Gemini via litellm)**: Costs depend on usage; billed directly by whichever provider's API key is configured; configurable limits via `MAX_APPLICATIONS_PER_DAY` and `DISCOVERY_MAX_JOBS_PER_RUN`
- **Greenhouse/Lever APIs**: Free (public)
- **Firestore**: Free tier (1 GiB storage + 50K reads/day) — essentially free at low usage
- **GCP Cloud Functions**: Free tier covers light usage

---
