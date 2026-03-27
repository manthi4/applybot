# Dashboard

Central web interface for monitoring and controlling ApplyBot. Two components:

1. **FastHTML frontend** (`frontend.py`) — Full dashboard UI with PicoCSS styling, HTMX interactivity, and a dark slate-blue/red theme.
2. **FastAPI REST API** (`api.py`) — Standalone REST API for programmatic access (used by external tools, not by the frontend).

## Files

```
dashboard/
├── frontend.py       # App setup, route registration, entrypoint
├── theme.py          # Dark slate-blue + slate-red PicoCSS theme overrides
├── components.py     # Reusable UI components (nav, page, cards, forms, badges)
├── pages/
│   ├── __init__.py
│   ├── overview.py   # Overview page — stats cards and pipeline progress
│   ├── jobs.py       # Job queue — list, filter, approve, skip
│   ├── apps.py       # Applications — list, filter, approve, draft
│   └── profile.py    # Profile — view and edit user profile
├── api.py            # FastAPI REST API (10 endpoints)
└── README.md
```

## Architecture

### Frontend (FastHTML)

The frontend uses a modular architecture:

- **`theme.py`** — CSS custom properties overriding PicoCSS defaults. Dark slate-blue backgrounds (#0f172a, #1e293b), slate-red accents (#dc2626), and colored status badges. Exports `theme_headers` tuple for `fast_app(hdrs=...)`.

- **`components.py`** — Reusable building blocks:
  - Layout: `nav()`, `page()`, `alert()`
  - Data display: `stat_card()`, `progress_table()`, `status_badge()`
  - Forms: `filter_form()`
  - Cards: `detail_card()`, `action_buttons()`, `confirmed_card()`, `collapsible_text()`

- **`pages/`** — Each page module exports a `register(rt)` function that decorates route handlers onto the FastHTML route table.

- **Health check** — `GET /healthz` returns plain text `ok`. Used by Cloud Run startup and liveness probes.

- **`frontend.py`** — Coordinator: creates the `fast_app`, applies the theme, calls `register(rt)` for each page module, and provides the `main()` entrypoint.

### Pages

1. **Overview** (`/`) — Stats cards, pipeline progress bars, application status breakdown
2. **Job Queue** (`/jobs`) — Filterable job list with HTMX-powered approve/skip actions
3. **Applications** (`/apps`) — Applications by status with cover letter, answers, and review actions
4. **Profile** (`/profile`) — Name/email/summary editor + full profile JSON display

The frontend queries the database directly using `get_session()` from `models.base` — no HTTP calls to the REST API. Interactive actions (approve, skip, status changes) use HTMX partial page swaps.

### Running the Dashboard

```bash
applybot serve
applybot serve --host 0.0.0.0 --port 8080 --reload

# Or directly:
python -m applybot serve
```

## REST API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/jobs` | List jobs (filter: `status`, `min_score`; `limit` <= 500) |
| GET | `/jobs/{job_id}` | Job details |
| POST | `/jobs/{job_id}/approve` | Mark job as APPROVED |
| POST | `/jobs/{job_id}/skip` | Mark job as SKIPPED |
| GET | `/applications` | List applications (filter: `status`; `limit` <= 500) |
| GET | `/applications/{app_id}` | Application details |
| POST | `/applications/{app_id}/review` | Update application status (body: `{"action": "approve"}`) |
| GET | `/profile` | Current user profile |
| PUT | `/profile` | Update profile fields |
| GET | `/dashboard/summary` | Counts by status for jobs and applications |

### Running the API

```bash
applybot serve-api
applybot serve-api --host 0.0.0.0 --port 8001 --reload
```

## CLI

```bash
# Start dashboard (FastHTML, default port 8000)
applybot serve

# Start REST API only (FastAPI, default port 8001)
applybot serve-api
```

## Boundaries

- **Depends on**: `models` (ORM), `config` (database URL), `tracking` (status transitions)
- **Does not depend on**: LLM, Discovery, Application, or Profile modules directly
- **Used by**: End users via browser (frontend), other services via REST API
- The frontend accesses the database directly; the REST API is an independent interface


## Cloud Deployment

### Dashboard → Cloud Run

The FastHTML + FastAPI app (`applybot serve`) is hosted on **GCP Cloud Run**:
- Build a Docker image from the project root and push to Artifact Registry
- Deploy as a Cloud Run service with:
  - `GCP_PROJECT_ID` injected as an environment variable (for Firestore)
  - Service account with `roles/datastore.user` for Firestore access
- Expose on HTTPS via the Cloud Run-managed URL

### Secrets

All sensitive config is stored in GCP Secret Manager and mounted as environment variables in Cloud Run:
- `ANTHROPIC_API_KEY`
- `SERPAPI_KEY`
- `GOOGLE_APPLICATION_CREDENTIALS` (Gmail OAuth)
