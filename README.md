# ApplyBot

A modular, cloud-hosted Python system that uses Claude agents to discover ML/robotics jobs daily, prepare tailored applications (resume + answers), and present them for human review before submission. GCP for hosting, Firestore for persistence, paid aggregator APIs for scraping, Anthropic SDK for AI, and a FastHTML dashboard.

---

## How It Works

ApplyBot is organized as a pipeline with four main stages, a central dashboard, and a cloud scheduler:

```
Profile ──→ Discovery ──→ Application Prep ──→ Tracking
                              ↕                    ↕
                          Dashboard            Gmail
                              ↕
                       Cloud Scheduler
```

1. **Profile** — Maintains a structured reference document of your skills, experiences, and interests. All other stages consult this. On first run, a bootstrap agent parses your existing resume, extracts a structured profile, identifies gaps, and runs an interactive CLI flow to fill them in.
2. **Discovery** — Searches multiple job boards daily using LLM-generated queries, deduplicates results with fuzzy matching, and uses Claude to rank jobs by relevance to your profile (0-100 score with reasoning).
3. **Application** — For each approved job, tailors your resume (rephrase/reorder only — never fabricate), drafts answers to common application questions, generates a cover letter, and flags any profile gaps that need human input. Creates an Application record for review.
4. **Tracking** — Manages application lifecycle through a validated state machine (DRAFT → READY_FOR_REVIEW → APPROVED → SUBMITTED → RECEIVED → INTERVIEW/OFFER/REJECTED). Scans Gmail to auto-detect status updates from applied-to companies.
5. **Dashboard** — FastHTML UI for reviewing job queue, managing applications, editing profile, and viewing pipeline statistics. Protected by TOTP authentication.
6. **Scheduler** — GCP Cloud Functions triggered by Cloud Scheduler for automated daily execution.

**Human-in-the-loop**: The agent prepares everything, but never submits without explicit approval. Safety guardrail: the agent never submits without explicit approval.

---

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Language | Python 3.12+ | black/ruff/mypy configured |
| LLM | Anthropic Claude (direct SDK) | Sonnet for cost-efficient tasks, Opus for complex reasoning; no LangChain |
| Database | Google Cloud Firestore | Serverless NoSQL document database; schema-less, no migrations needed |
| Frontend | FastHTML + PicoCSS + HTMX | Lightweight Python-native UI; no JS build step |
| Job Scraping | SerpAPI, Greenhouse API, Lever API, lxml | Paid aggregator + free public APIs |
| Resume | python-docx | Parse and generate .docx preserving formatting |
| Deduplication | rapidfuzz | Fuzzy token_sort_ratio matching (threshold 85) |
| Cloud | GCP Cloud Functions + Cloud Scheduler + Cloud Run | Daily automation + dashboard hosting |

---

## Project Structure

```
applybot/
├── README.md               # This file
├── STATUS.md               # Current progress and next steps
├── DEPLOY.md               # Full deployment guide (manual + CI/CD)
├── core_idea.md            # Original project vision
├── pyproject.toml          # Dependencies and tool config
├── data/                   # Local data (resume, exports)
├── .github/workflows/
│   ├── terraform.yml       # Terraform plan/apply CI workflow
│   └── docker.yml          # Docker build & push CI workflow
├── infra/                  # Terraform IaC (GCP Cloud Run, GCS data bucket, etc.)
├── src/applybot/
│   ├── config.py           # Pydantic Settings (env-based)
│   ├── models/             # Pydantic models + Firestore CRUD (Job, Application, UserProfile)
│   ├── llm/                # Anthropic Claude SDK wrapper
│   ├── profile/            # Profile CRUD + .docx resume parsing/generation
│   ├── discovery/          # Multi-source job scraping + dedup + ranking
│   │   └── scrapers/       # Pluggable scraper implementations
│   ├── application/        # Resume tailoring + Q&A + cover letters
│   ├── tracking/           # State machine + Gmail integration
│   └── dashboard/          # FastHTML UI (TOTP-authenticated)
├── scheduler/              # GCP Cloud Function entry points (planned)
└── tests/                  # pytest suite
```

Each component under `src/applybot/` has its own README describing its purpose, API, and boundaries.

---

## Architecture

### Data Flow

```
┌─────────────────────────────────────────────┐
│         Dashboard (FastHTML)                  │
│  TOTP-authenticated UI for jobs, apps,       │
│  profile, and pipeline statistics            │
└──────────────┬──────────────────────────────┘
               │
┌──────────────┴──────────────────────────────┐
│           Tracking Layer                     │
│  State machine + Gmail email classification  │
│  + Notifications (email/Slack)               │
└──────────────┬──────────────────────────────┘
               │
┌──────────────┴──────────────────────────────┐
│       Application Preparation                │
│  Resume Tailor → Q&A → Cover Letter          │
│  (honesty guardrail: no fabrication)         │
│  Human review before submission              │
└──────────────┬──────────────────────────────┘
               │
┌──────────────┴──────────────────────────────┐
│         Discovery Pipeline (async)           │
│  Query Builder → Scrapers (parallel) →       │
│  Deduplicator → Ranker → Save to DB         │
└──────────────┬──────────────────────────────┘
               │
┌──────────────┴──────────────────────────────┐
│    Shared Foundation                         │
│  Models (Firestore) · LLM Client · Profile · Config│
└─────────────────────────────────────────────┘
```

### Cross-Cutting Dependencies

- **LLM Client** — Used by: Query Builder, Ranker, Resume Tailor, Question Answerer, Gmail classifier, Cover Letter generator
- **Profile** — Central source of truth consulted by Discovery (query building, ranking) and Application (tailoring, answering)
- **Models** — Shared Firestore data layer accessed by all components

---

## Data Models

### Job

| Field | Type | Notes |
|---|---|---|
| id | str | Firestore document ID |
| title | str | Job title |
| company | str | Company name |
| location | str | Job location |
| description | str | Full job description |
| url | str | Application URL |
| source | JobSource enum | SERPAPI, GREENHOUSE, LEVER, EU_REMOTE_JOBS, MANUAL |
| posted_date | str | When the job was posted |
| discovered_date | str | When we found it (ISO format) |
| relevance_score | int | 0-100 score from ranker |
| relevance_reasoning | str | Ranker's explanation |
| status | JobStatus enum | NEW → REVIEWING → APPROVED → APPLIED / SKIPPED / REJECTED |

### UserProfile

| Field | Type | Notes |
|---|---|---|
| name | str | Full name |
| email | str | Contact email |
| summary | str | Professional summary |
| skills | list | Structured skills data |
| experiences | list | Work experience entries |
| education | list | Education entries |
| preferences | dict | Job preferences (roles, locations, salary, etc.) |
| resume_path | str | Path to base .docx resume |

Stored as a singleton document (`"default"`) in the `profiles` collection.

### Application

| Field | Type | Notes |
|---|---|---|
| id | str | Firestore document ID |
| job_id | str | Which job this applies to |
| tailored_resume_path | str | Path to generated .docx |
| cover_letter | str | Generated cover letter |
| answers | dict | question → answer pairs |
| status | ApplicationStatus | DRAFT → READY_FOR_REVIEW → APPROVED → SUBMITTED → RECEIVED → INTERVIEW → OFFER / REJECTED / WITHDRAWN |
| created_at | str | When the application was prepared (ISO format) |
| submitted_at | str | When it was actually submitted (ISO format) |

### ApplicationStatusUpdate

| Field | Type | Notes |
|---|---|---|
| id | str | Firestore document ID |
| application_id | str | References an Application |
| status | ApplicationStatus | New status |
| source | UpdateSource | MANUAL, GMAIL, SYSTEM |
| details | str | Optional notes |
| timestamp | str | When the change occurred (ISO format) |

---

## Component Details

### LLM Client (`llm/`)

Thin wrapper around the Anthropic SDK providing three call patterns:

- **`complete(prompt, system, model, temperature)`** → `str` — Simple text completion
- **`structured_output(prompt, output_type, system, model)`** → `T` — Returns a Pydantic model; auto-strips markdown code fences from JSON
- **`with_tools(prompt, tools, system, model)`** → `Message` — Tool-use call returning the full Anthropic Message for inspection

Configurable model selection (sonnet for fast/cheap tasks, opus for complex reasoning). Module-level singleton `llm = LLMClient()`.

### Profile (`profile/`)

**ProfileManager** — CRUD operations for the UserProfile table:
- `get_profile()`, `get_or_create_profile(name, email)`, `update_profile(**kwargs)`
- `get_skills()`, `export_profile_json(path)`, `import_profile_json(path)`

**Resume** — .docx parsing and generation:
- `parse_resume(path)` → `ResumeData` (name, contact_info, sections with title + content)
- `generate_resume(data, template_path, output_path)` → creates tailored .docx preserving template formatting

**Bootstrap flow** (planned): On first run, parse existing resume → extract structured profile → store in DB → agent identifies gaps → interactive CLI to fill them in.

### Discovery (`discovery/`)

**Pipeline**: Query Builder → Scrapers (parallel, async) → Deduplicator → Ranker → Save to DB

**Query Builder** — Uses Claude + user profile to generate 6 varied search queries (e.g., "machine learning engineer robotics", "ML infrastructure", "applied ML robotics"). Falls back to sensible defaults if no profile exists.

**Scrapers** — Pluggable via `BaseScraper` ABC. Each returns `list[RawJob]`:

| Scraper | Source | API/Method | Coverage |
|---|---|---|---|
| SerpAPIScraper | Google Jobs | SerpAPI paid API | LinkedIn, Indeed, Glassdoor aggregated |
| GreenhouseScraper | Greenhouse | Public boards API (`boards-api.greenhouse.io`) | Companies using Greenhouse ATS |
| LeverScraper | Lever | Public postings API (`api.lever.co`) | Companies using Lever ATS |
| EuRemoteJobsScraper | EuRemoteJobs | HTML scraping with lxml | EU remote positions |
| *(Workday)* | *(deferred)* | *Complex, per-company tenants* | *Deferred to future phase* |

All scrapers run concurrently via `asyncio.gather()`. One scraper failing doesn't block others.

**Deduplicator** — Fuzzy matching on (title + company + location) using rapidfuzz `token_sort_ratio` with threshold of 85. Normalizes URLs by stripping tracking parameters. Merges duplicates, keeps earliest discovered_date.

**Ranker** — Claude evaluates each job against the user profile in batches of 5. Returns `(job, score: 0-100, reasoning: str)`. Filters out jobs below configurable threshold (default: 50).

**Orchestrator** — `run_discovery()` ties it all together and returns `DiscoveryResult` with counts: total_scraped, after_dedup, above_threshold, new_jobs_saved, top_matches.

### Application (`application/`)

**Resume Tailor** — Input: job description + user profile + base resume. Claude analyzes job requirements, generates a `TailoringPlan` (summary rewrite + per-section edits), then applies it to produce a tailored .docx.

**Strict guardrail**: The agent can only reorder/rephrase existing experiences from the profile. It must NOT fabricate skills, experiences, or qualifications.

**Question Answerer** — Drafts answers to common application questions:
- "Why are you interested in this role?"
- "Why do you want to work at {company}?"
- "Describe your most relevant experience for this role."
- "What is your greatest strength related to this position?"

Custom questions can be added per job. If the profile lacks required info, returns `ProfileGap` objects (question + context) for human input.

**Cover Letter Generator** — Claude writes a 3-4 paragraph letter using only real profile data.

**Preparer** — Orchestrates the full flow: tailor resume → answer questions → generate cover letter → create Application record (status=READY_FOR_REVIEW). Also has `prepare_all_approved()` to batch-process all approved jobs.

**Human Review** — Dashboard shows job details side-by-side with tailored resume (downloadable .docx) and draft answers. User can approve, edit, reject, or request re-generation.

### Tracking (`tracking/`)

**State Machine** — Enforced valid transitions:

```
DRAFT → READY_FOR_REVIEW, WITHDRAWN
READY_FOR_REVIEW → APPROVED, DRAFT, WITHDRAWN
APPROVED → SUBMITTED, WITHDRAWN
SUBMITTED → RECEIVED, REJECTED, WITHDRAWN
RECEIVED → INTERVIEW, REJECTED, WITHDRAWN
INTERVIEW → OFFER, REJECTED, WITHDRAWN
OFFER → WITHDRAWN
REJECTED → (terminal)
WITHDRAWN → (terminal)
```

Every transition creates an `ApplicationStatusUpdate` audit record with source (MANUAL/GMAIL/SYSTEM) and timestamp.

**Gmail Integration** — Google Gmail API with OAuth2 (offline access):
1. Looks up companies from applied-to applications
2. Searches Gmail: `from:{company} OR subject:{company} newer_than:3d`
3. Claude classifies each email → `EmailClassification` (is_application_related, status, confidence, summary)
4. If confidence ≥ 0.7 and application-related → auto-updates application status

**Notifications** (planned) — Email/Slack alerts when: new high-relevance jobs found, applications ready for review, status changes detected.

### Dashboard (`dashboard/`)

**FastHTML Frontend** — Pages:
- **Overview** (`/`) — Stats cards, pipeline progress bars, application status breakdown
- **Job Queue** (`/jobs`) — Filterable job list with HTMX-powered approve/skip actions
- **Applications** (`/apps`) — Applications by status with cover letter, answers, review actions
- **Profile** (`/profile`) — Name/email/summary form + full profile JSON display

**Authentication** — All routes except `/healthz` are protected by TOTP. Set `DASHBOARD_TOTP_SECRET` (Base32 secret) to enable. Run `applybot setup-auth` to generate a secret and scan the QR code with any authenticator app. Sessions last 24 hours (signed cookie).

---

## Configuration

Pydantic Settings, loading from environment variables or a `.env` file:

```env
# Required
ANTHROPIC_API_KEY=sk-ant-...
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
ANTHROPIC_MODEL_FAST=claude-sonnet-4-20250514     # Cost-efficient tasks
ANTHROPIC_MODEL_SMART=claude-sonnet-4-20250514    # Complex reasoning
ANTHROPIC_MAX_RETRIES=3
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
| Direct Anthropic SDK (no LangChain) | Simpler, fewer deps, more debuggable |
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

## Cloud Deployment Plan

### GCP Cloud Functions

| Function | Trigger | Schedule | Purpose |
|---|---|---|---|
| `discovery_fn` | Cloud Scheduler | Daily at 8am | Run discovery orchestrator, send notification with summary |
| `application_fn` | Pub/Sub or Cloud Scheduler | 2x daily | Prepare applications for approved jobs |
| `tracking_fn` | Cloud Scheduler | 2x daily | Scan Gmail for status updates |

### Infrastructure

- **Database**: Google Cloud Firestore (FIRESTORE_NATIVE mode). Serverless, no provisioning or connection pools.
- **Dashboard**: GCP Cloud Run (FastHTML), scales 0–1
- **Secrets**: GCP Secret Manager for API keys
- **Auth**: Service account with `roles/datastore.user` for Firestore access
- **Scheduling**: Cloud Scheduler cron jobs

### CI/CD (GitHub Actions)

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

**Required GitHub Secrets:** `GCP_SA_KEY`, `GCP_PROJECT_ID`, `TF_VAR_ANTHROPIC_API_KEY`, `TF_VAR_SERPAPI_KEY`.
**Optional GitHub Variables:** `GCP_REGION` (default: `us-central1`), `IMAGE_TAG` (default: `latest`).

See [DEPLOY.md](DEPLOY.md) § "CI/CD with GitHub Actions" for full setup instructions (GCS bucket for Terraform state, CI service account creation, secrets configuration).

---

## Cost Considerations

- **SerpAPI**: ~$50/month for 5,000 searches
- **Claude API**: Costs depend on usage; configurable limits via `MAX_APPLICATIONS_PER_DAY` and `DISCOVERY_MAX_JOBS_PER_RUN`
- **Greenhouse/Lever APIs**: Free (public)
- **Firestore**: Free tier (1 GiB storage + 50K reads/day) — essentially free at low usage
- **GCP Cloud Functions**: Free tier covers light usage

Cost tracking per pipeline run is planned but not yet implemented.

---

## Scope & Exclusions

**In scope (prepare & review)**:
- Automated job discovery across multiple boards
- AI-powered resume tailoring and application preparation
- Human review and approval workflow
- Application lifecycle tracking
- Gmail-based status detection

**Explicitly excluded**:
- **Auto-submission** — Actually filling and submitting application forms on job sites. Too fragile, varies per site. Some sites have apply APIs, others would need browser automation (Playwright). Deferred.
- **Workday scraper** — Complex, each company has a different Workday tenant. Deferred.
- **Mobile app** — Desktop/web dashboard only for now.
- **Multi-user support** — Single-user system.

---

## Implementation Phases

### Phase 1: Foundation ✅
Project skeleton, shared models, config, database, LLM client wrapper.

### Phase 2: Profile ✅
Profile manager (CRUD, JSON import/export), resume parser/generator (.docx).

### Phase 3: Discovery ✅
Scraper interface + 4 implementations (SerpAPI, Greenhouse, Lever, EuRemoteJobs), query builder, deduplicator, ranker, orchestrator.

### Phase 4: Application ✅
Resume tailoring agent (with honesty guardrail), question answerer, cover letter generator, application preparer orchestrator.

### Phase 5: Tracking ✅
Application tracker state machine, Gmail integration with email classification.

### Phase 6: Dashboard ✅
FastHTML frontend (4 pages, PicoCSS + HTMX), TOTP session authentication.

### Phase 7: Cloud Deployment 🔧
GCP Cloud Run, Firestore, Secret Manager, Artifact Registry — Terraform IaC ready. GitHub Actions CI/CD workflows for Terraform and Docker. Cloud Scheduler configured.

---

## Future Work

- **CLI entrypoints** — `python -m applybot.cli discover/prepare/serve`
- **Profile bootstrap flow** — Import resume → extract profile → fill gaps interactively
- **Company target lists** — Curated list of robotics/ML company slugs for Greenhouse/Lever (could also discover from SerpAPI results)
- **Notification system** — Email/Slack alerts for new jobs, ready applications, status changes
- **Workday scraper** — Per-company tenants, complex integration
- **Auto-submission** — Form filling via apply APIs or browser automation (Playwright)
- **Cost tracking** — Per-run visibility into LLM API and scraper costs
- **Google OAuth setup** — Automated consent flow script for Gmail integration
