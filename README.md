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
    * **Profile** - Maintains a structured reference document of the user's skills, experiences, and interests. Essentially a stucured representatoin of their resume with any additional information they provide.
    * **Job Postings** - Stores all the job postings that have been posted with schema <<>>
    * **Applications** - Stores all the applications that have been created as well as their current status <<>>
        * Links each application with the UUID of the job posting it's for.
        * Applications also have an associated "status" field. Either "review, approved, applied, rejected, or accepted"
4. **Dashboard** — Web UI for reviewing and approving discoverd jobs, managing applications, editing profile, and viewing pipeline statistics.

5. **LLM Engine** - Modular API Key based engine to serve the rest of the components. It needs to expose a consistent well documented API surface for the remaining components to access. But under the hood it should allow the user to drop in their own personal LLM service's API Key and URL.

**Human-in-the-loop**: The agent prepares everything, but never submits without explicit approval. Safety guardrail: the agent never submits without explicit approval.

---

## Project Structure

```
applybot/
├── requirements.txt        #
├── AGENTS.md               #
├── README.md               # This file
├── DEPLOY.md               # Full deployment guide (manual + CI/CD)
├── pyproject.toml          # Dependencies and tool config
├── data/                   # Local data (resume, exports)
├── .github/workflows/
│   ├── terraform.yml       # Terraform plan/apply CI workflow
│   └── docker.yml          # Docker build & push CI workflow
├── infra/                  # Terraform IaC (GCP Cloud Run, GCS data bucket, etc.)
├── src/applybot/
│   ├── application/        # Applicatio prep functions.
│   ├── dashboard/          #
│   ├── discovery/          # Job discovery functions.
│   ├── llm/                #
│   ├── models/             # Pydantic models + Firestore CRUD (Job, Application, UserProfile)
│   ├── config.py           # Pydantic Settings (env-based)
└── tests/                  # pytest suite

```

Each component has its own README describing its purpose, API, and boundaries. It also has its own requirements.in and requirements-dev.in which get compiled into the top level requirements.txt

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

Pydantic Settings, loading from environment variables or a `.env` file:

```env
# Required
GCP_PROJECT_ID=your-gcp-project-id
SERPAPI_KEY=...

# GCP Project (for Firestore; falls back to ADC)
GCP_PROJECT_ID=your-gcp-project-id

# Gmail (optional, for tracking)
GOOGLE_APPLICATION_CREDENTIALS=path/to/credentials.json

# Discovery tuning
DISCOVERY_RELEVANCE_THRESHOLD=50    # Min relevance score (0-100)
DISCOVERY_MAX_JOBS_PER_RUN=100

# Application limits
MAX_APPLICATIONS_PER_DAY=10

# LLM models
LLM_PROVIDER=gemini                          # gemini (default) or anthropic
VERTEX_REGION=us-east5                       # Vertex AI region (both providers)
GEMINI_MODEL_FAST=gemini-2.0-flash           # Cost-efficient tasks
GEMINI_MODEL_SMART=gemini-2.5-pro            # Complex reasoning
# To switch to Claude on Vertex AI instead:
# LLM_PROVIDER=anthropic
# ANTHROPIC_MODEL_FAST=claude-sonnet-4-6
# ANTHROPIC_MODEL_SMART=claude-sonnet-4-6
```

---

## Setup

```bash
# Install (with dev tools and dashboard)
pip install -e ".[dev,dashboard]"

# Initialize database
python -c "from applybot.models.base import init_db; init_db()"

# Run tests
pytest
```

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| Claude via Vertex AI (no LangChain) | Better GCP integration, ADC auth, no separate API key needed |
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

ApplyBot is hosted on **Google Cloud Platform** in a single GCP project (ID configured at deploy time via Terraform). The default region is `us-central1`; Vertex AI LLM calls use `us-east5`.

### Compute Services

| Service | GCP Product | What it runs | Entry point |
|---|---|---|---|
| **Dashboard** | Cloud Run | FastHTML web UI on port 8000 | Docker image from Artifact Registry |
| **Discovery Pipeline** | Cloud Functions (Gen 2) | Daily job scraping + dedup + ranking | `handle_discovery` in `main.py` |

The dashboard scales 0–1 (serverless, pay-per-use). The discovery function and application preparation are triggered manually via the **"Build Approved Applications"** button on the dashboard.


---

## Cost Considerations

- **SerpAPI**: ~$50/month for 5,000 searches
- **Claude via Vertex AI**: Costs depend on usage; billed through GCP; configurable limits via `MAX_APPLICATIONS_PER_DAY` and `DISCOVERY_MAX_JOBS_PER_RUN`
- **Greenhouse/Lever APIs**: Free (public)
- **Firestore**: Free tier (1 GiB storage + 50K reads/day) — essentially free at low usage
- **GCP Cloud Functions**: Free tier covers light usage

---
