# Dashboard

Central web interface for monitoring and controlling ApplyBot. A FastHTML server with PicoCSS styling, HTMX interactivity, and a dark slate-blue/red theme. Protected by TOTP authentication.

## Files

```
dashboard/
├── frontend.py       # App setup, auth middleware, login/logout routes, entrypoint
├── config.py         # Dashboard settings — env-only (no .env); independent of root applybot.config
├── theme.py          # Dark slate-blue + slate-red PicoCSS theme overrides
├── Dockerfile        # Cloud Run image — multi-stage, amd64, runs the dashboard module directly
├── docker-compose.yml# Local Docker run — builds the Dockerfile, injects all config as env vars
├── requirements.in   # Runtime deps for this module (mirrors root pyproject.toml)
├── requirements-dev.in # Dev/test deps for this module
├── components/     # Reusable UI components package
│   ├── __init__.py        # Re-exports the public API (nav, page, cards, forms, badges)
│   ├── layout.py          # nav(), page(), alert()
│   ├── data_display.py    # stat_card(), progress_table(), status_badge()
│   ├── forms.py           # filter_form()
│   └── cards.py           # detail_card(), action_buttons(), confirmed_card(), collapsible_text()
├── services/         # Dashboard-local domain logic + HTTP clients for other services
│   ├── __init__.py
│   ├── resume.py          # parse_resume() / ResumeData — heuristic resume parser
│   ├── enrichment.py      # fire-and-forget LLM profile enrichment after upload
│   ├── discovery.py       # trigger_discovery() — HTTP client for the discovery Cloud Function
│   └── application.py     # trigger_application_preparation() — HTTP client for the application-preparer Cloud Function
├── pages/
│   ├── __init__.py
│   ├── overview.py   # Overview page — stats cards and pipeline progress
│   ├── jobs.py       # Job queue — staging area, build-approved, list, filter, approve, skip
│   ├── apps.py       # Applications — list, filter, approve, withdraw, edit cover letter/answers, re-tailor resume
│   └── profile.py    # Profile — view and edit user profile
└── README.md
```

## Architecture

### Frontend (FastHTML)

The frontend uses a modular architecture:

- **`theme.py`** — CSS custom properties overriding PicoCSS defaults. Dark slate-blue backgrounds (#0f172a, #1e293b), slate-red accents (#dc2626), and colored status badges. Exports `theme_headers` tuple for `fast_app(hdrs=...)`.

- **`components/`** — Reusable UI building blocks, split by category (re-exported from `__init__.py` so pages import as `from applybot.dashboard.components import <name>`):
  - `layout.py`: `nav()`, `page()`, `alert()`
  - `data_display.py`: `stat_card()`, `progress_table()`, `status_badge()`
  - `forms.py`: `filter_form()`
  - `cards.py`: `detail_card()`, `action_buttons()`, `confirmed_card()`, `collapsible_text()`

- **`pages/`** — Each page module exports a `register(rt)` function that decorates route handlers onto the FastHTML route table.

- **Health check** — `GET /healthz` returns plain text `ok`. Used by Cloud Run startup and liveness probes.

- **`frontend.py`** — Coordinator: creates the `fast_app`, applies the theme, calls `register(rt)` for each page module, and provides the `main()` entrypoint.

### Pages

1. **Overview** (`/`) — Stats cards, pipeline progress bars, application status breakdown, plus a **"Run Discovery Now"** button (`POST /discover`) that triggers the `applybot-discovery` Cloud Function over HTTP (via `services/discovery.py`) with a loading spinner. Requires `DISCOVERY_FUNCTION_URL` to be set.
2. **Job Queue** (`/jobs`) — Approved jobs queued for application generation, plus a filterable browse list.
   - **Staging Area** — Panel showing approved jobs queued for application generation, with a **"Build Approved Applications"** button (`POST /jobs/build-approved`) that triggers the `applybot-application-preparer` Cloud Function over HTTP (via `services/application.py`) with a loading spinner during the (potentially slow) LLM call. Requires `APPLICATION_PREPARER_FUNCTION_URL` to be set. An **"Unstage All"** button (`POST /jobs/unstage-all`) returns all approved jobs to NEW.
   - **Browse Jobs** — Filterable job list (defaults to NEW) with HTMX-powered approve/skip actions. Compact inline approve/skip buttons sit on the right side of each job tile header. Approving or skipping a job uses OOB swaps to refresh both the staging area and the browse list in one response.
3. **Applications** (`/apps`) — Applications by status with inline editing: edit the cover letter and Q&A answers, re-tailor the resume, download the tailored resume, and approve/withdraw. Terminal statuses (rejected/withdrawn) render read-only.
4. **Profile** (`/profile`) — Full profile editor with multiple sections:
   - **Basic Information**: Edits name + summary only (`POST /profile`).
   - **Contact Information**: Separate section editing email, LinkedIn, phone, GitHub (`POST /profile/contact`). Email is no longer under Basic Info.
   - **Resume upload**: Upload `.docx`, `.pdf`, or `.md` (max 10 MB) — auto-parsed with `parse_resume()` (`services/resume.py`), stored via the `applybot.storage` layer as object `resumes/resume.<ext>` (GCS in production when `GCS_BUCKET_NAME` is set, local `data/` fallback in dev); `profile.resume_path` holds the object name. Heuristic parse backfills empty name/summary and extracts an email; `_map_resume_to_profile()` maps resume sections to profile fields by keyword. **Parsing is heuristic-only (no LLM).** After the heuristic save, a fire-and-forget background task (`services/enrichment.py`) asks the LLM to enrich the profile. PDF support requires a text-based PDF (scanned PDFs won't work).
   - **Resume download**: `GET /profile/resume` — serves the stored resume via `get_download_response()` from `applybot.storage` (format preserved: `.docx`, `.pdf`, or `.md`).
   - **Skills / Experience / Education / Preferences**: Structured display + collapsible edit forms (`Details`/`Summary`) with JSON textarea editors and schema placeholder examples
   - **Raw JSON**: Collapsible full profile JSON view
   - **Flash messages**: Success/error alerts after each action
   - **Completeness indicator**: N/8 progress bar — the 8 fields are: name, contact_info, summary, skills, experiences, education, preferences, resume_path

   Routes: `GET /profile`, `POST /profile` (basic info), `POST /profile/contact` (contact info), `GET /profile/resume` (download), `POST /profile/resume` (upload), `POST /profile/details` (skills/experiences/education/preferences)

The frontend queries the database directly using Firestore CRUD functions from models. Interactive actions (approve, skip, status changes, build) use HTMX partial page swaps.

### Authentication

All routes except `/healthz` are protected by TOTP (Time-Based One-Time Password) authentication.

- When `DASHBOARD_TOTP_SECRET` is set: visiting any page redirects to `/login` if not authenticated. Enter the 6-digit code from your authenticator app (Google Authenticator, Authy, etc.) to access the dashboard. Sessions last 24 hours.
- When `DASHBOARD_TOTP_SECRET` is not set (dev mode): auth is disabled — the dashboard is open.

Session state is stored in a signed cookie (derived from the TOTP secret). The `/login` and `/healthz` routes are always open.

To set up authentication:
```bash
# Generate a new TOTP secret for your authenticator app (prints secret + otpauth URI)
applybot setup-auth
```

Then place the printed `DASHBOARD_TOTP_SECRET` value in **both** places:
- **Your authenticator app** (Google Authenticator, Authy, 1Password) — enter the secret manually so it can generate login codes.
- **The server** — so it can verify those codes:
  - **Local dev**: add `DASHBOARD_TOTP_SECRET=<base32-secret>` to your `.env`.
  - **Cloud Run (production)**: set `dashboard_totp_secret` in `infra/terraform.tfvars` (copy from `terraform.tfvars.example`). On `terraform apply` this is written to Secret Manager (`infra/secrets.tf`) and mounted into Cloud Run as the `DASHBOARD_TOTP_SECRET` env var (`infra/cloud_run.tf`).

Both sides must hold the identical secret — TOTP is symmetric. If `DASHBOARD_TOTP_SECRET` is unset on the server, auth is disabled (dev mode).

### Running the Dashboard

**Local development:**
```bash
applybot serve                 # http://127.0.0.1:8000 (reads PORT env / settings.port)
applybot serve --reload        # auto-reload on code changes
applybot serve --host 0.0.0.0  # bind all interfaces
```
Equivalent: `python -m applybot.dashboard.frontend`.

**Cloud Function URLs (local dev):** The "Run Discovery Now" and "Build
Approved Applications" buttons trigger Cloud Functions over HTTP via
`services/discovery.py` and `services/application.py`. Both require their
function URL to be set:

- `DISCOVERY_FUNCTION_URL` — the `applybot-discovery` Cloud Function.
- `APPLICATION_PREPARER_FUNCTION_URL` — the `applybot-application-preparer`
  Cloud Function.

For local development, point either at a locally running `functions-framework`
instance (or the deployed function URL). An unset URL is a hard error — there
is no in-process fallback, by design. The call is authenticated with an OIDC
identity token fetched via Application Default Credentials (`gcloud auth
application-default login` locally); the Cloud Run service account holds
`roles/cloudfunctions.invoker` on each function in production.

**Docker (matches Cloud Run image):**
```bash
docker build -f src/applybot/dashboard/Dockerfile -t applybot .
docker run -p 8000:8000 applybot   # serves on 0.0.0.0:8000 via `python -m applybot.dashboard.frontend`
```

**Docker Compose (env-only — no .env loaded):** `docker-compose.yml` builds the
Dockerfile and injects every setting as a real environment variable. Export the
vars you need (see the file header), then:
```bash
docker compose -f src/applybot/dashboard/docker-compose.yml up --build
```

Place your GCP service-account JSON at the repo root as `service-account.json`
(or change the host path in `docker-compose.yml`). It is mounted read-only at
`/app/service-account.json` inside the container, which is what
`GOOGLE_APPLICATION_CREDENTIALS` should point to.

**Cloud Run:** pushes to Cloud Run on every commit to `main` whose message contains `--docker` (workflow `.github/workflows/docker.yml`). The image is built from the repo root with the dashboard Dockerfile, pushed to Artifact Registry, and deployed via `gcloud run deploy applybot`.

## Boundaries

- **Depends on**: `models` (Firestore CRUD), `config` (GCP project + TOTP secret + port + discovery function URL + application-preparer function URL), `application` (Build Approved Applications button triggers the `applybot-application-preparer` Cloud Function over HTTP via `services/application.py` — no direct import of the pipeline), `discovery` (Run Discovery button triggers the `applybot-discovery` Cloud Function over HTTP via `services/discovery.py` — no direct import of the pipeline), `llm` (profile enrichment after resume upload, via `services/enrichment.py`), `storage` (resume upload/download via GCS-with-local-fallback layer)

## Cloud Deployment

### Dashboard → Cloud Run

The FastHTML app (`python -m applybot.dashboard.frontend`) is hosted on **GCP Cloud Run**:
- Build a Docker image from the project root and push to Artifact Registry
- Deploy as a Cloud Run service with:
  - `GCP_PROJECT_ID` injected as an environment variable (for Firestore)
  - Service account with `roles/datastore.user` for Firestore access
- Expose on HTTPS via the Cloud Run-managed URL

### Secrets & environment

Cloud Run env vars (see `infra/cloud_run.tf`):
- `GCP_PROJECT_ID` (plain) — Firestore project
- `VERTEX_REGION` (plain) — Vertex AI region (Gemini + Anthropic)
- `GCS_BUCKET_NAME` (plain) — bucket for resume storage
- `SERPAPI_KEY` (Secret Manager) — job scraping
- `DASHBOARD_TOTP_SECRET` (Secret Manager) — dashboard auth
- `DISCOVERY_FUNCTION_URL` (plain) — URL of the `applybot-discovery` Cloud Function, invoked over HTTP with an OIDC identity token (the Cloud Run service account holds `roles/cloudfunctions.invoker` on the function)
- `APPLICATION_PREPARER_FUNCTION_URL` (plain) — URL of the `applybot-application-preparer` Cloud Function, invoked over HTTP with an OIDC identity token (the Cloud Run service account holds `roles/cloudfunctions.invoker` on the function). **Note:** only `applybot-discovery` is currently deployed in `infra/cloud_functions.tf`; the application-preparer Cloud Function entry point is not yet wired into Terraform, so the "Build Approved Applications" button will fail until it is deployed (or pointed at a local `functions-framework` instance).

Auth to GCP services is via the Cloud Run service account (ADC), not a credentials file. The service account has: `roles/datastore.user` (Firestore), `roles/secretmanager.secretAccessor`, `roles/aiplatform.user` (Vertex AI), and `roles/storage.objectAdmin` (GCS).
