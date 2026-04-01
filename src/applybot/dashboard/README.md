# Dashboard

Central web interface for monitoring and controlling ApplyBot. A FastHTML server with PicoCSS styling, HTMX interactivity, and a dark slate-blue/red theme. Protected by TOTP authentication.

## Files

```
dashboard/
├── frontend.py       # App setup, auth middleware, login/logout routes, entrypoint
├── theme.py          # Dark slate-blue + slate-red PicoCSS theme overrides
├── components.py     # Reusable UI components (nav, page, cards, forms, badges)
├── pages/
│   ├── __init__.py
│   ├── overview.py   # Overview page — stats cards and pipeline progress
│   ├── jobs.py       # Job queue — list, filter, approve, skip
│   ├── apps.py       # Applications — list, filter, approve, draft
│   └── profile.py    # Profile — view and edit user profile
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
2. **Job Queue** (`/jobs`) — Two-section layout:
   - **Staging Area** — Always-visible panel showing approved jobs queued for application generation, with a **"Build Approved Applications"** button that triggers `prepare_all_approved()` via HTMX. Shows a loading spinner during the (potentially slow) LLM call.
   - **Browse Jobs** — Filterable job list (defaults to NEW) with HTMX-powered approve/skip actions. Compact inline approve/skip buttons sit on the right side of each job tile header. Approving or skipping a job uses OOB swaps to refresh both the staging area and the browse list in one response.
3. **Applications** (`/apps`) — Applications by status with cover letter, answers, and review actions
4. **Profile** (`/profile`) — Full profile editor with multiple sections:
   - **Basic Info**: Edit name, email, summary
   - **Resume upload**: Upload `.docx`, `.pdf`, or `.md` files — auto-parsed with `parse_resume()`, saved to `data/resume.<ext>` (preserving the uploaded format), backfills empty name/summary; resume sections are mapped to profile fields by keyword matching via `_map_resume_to_profile()`. **Parsing is heuristic-only (no LLM).** PDF support requires a text-based PDF (scanned PDFs won't work).
   - **Skills / Experience / Education / Preferences**: Structured display + collapsible edit forms (`Details`/`Summary`) with JSON textarea editors and schema placeholder examples
   - **Raw JSON**: Collapsible full profile JSON view
   - **Flash messages**: Success/error alerts after each action
   - **Completeness indicator**: N/8 progress bar showing how many profile fields are filled
   - **Resume download**: `GET /profile/resume` — serves the uploaded resume file (format preserved: `.docx`, `.pdf`, or `.md`) as a file download

   Routes: `GET /profile`, `POST /profile` (basic info), `GET /profile/resume` (download), `POST /profile/resume` (upload), `POST /profile/details` (skills/experiences/education/preferences)

The frontend queries the database directly using Firestore CRUD functions from models. Interactive actions (approve, skip, status changes, build) use HTMX partial page swaps.

### Authentication

All routes except `/healthz` are protected by TOTP (Time-Based One-Time Password) authentication.

- When `DASHBOARD_TOTP_SECRET` is set: visiting any page redirects to `/login` if not authenticated. Enter the 6-digit code from your authenticator app (Google Authenticator, Authy, etc.) to access the dashboard. Sessions last 24 hours.
- When `DASHBOARD_TOTP_SECRET` is not set (dev mode): auth is disabled — the dashboard is open.

Session state is stored in a signed cookie (derived from the TOTP secret). The `/login` and `/healthz` routes are always open.

To set up authentication:
```bash
# Generate a new TOTP secret and QR code to scan with your authenticator app
applybot setup-auth

# Then add the secret to your .env (local) or GCP Secret Manager (production)
DASHBOARD_TOTP_SECRET=<base32-secret>
```

### Running the Dashboard

```bash
applybot serve
applybot serve --host 0.0.0.0 --port 8080 --reload

# Or directly:
python -m applybot serve
```

## Boundaries

- **Depends on**: `models` (Firestore CRUD), `config` (GCP project + TOTP secret), `tracking` (status transitions), `application` (for the Build Approved Applications button)
- **Does not depend on**: LLM, Discovery, Application, or Profile modules directly
- **Used by**: End users via browser (authenticated with TOTP)


## Cloud Deployment

### Dashboard → Cloud Run

The FastHTML app (`applybot serve`) is hosted on **GCP Cloud Run**:
- Build a Docker image from the project root and push to Artifact Registry
- Deploy as a Cloud Run service with:
  - `GCP_PROJECT_ID` injected as an environment variable (for Firestore)
  - Service account with `roles/datastore.user` for Firestore access
- Expose on HTTPS via the Cloud Run-managed URL

### Secrets

All sensitive config is stored in GCP Secret Manager and mounted as environment variables in Cloud Run:
- `VERTEX_REGION` (Vertex AI region — used by both Gemini and Anthropic providers)
- `SERPAPI_KEY`
- `GOOGLE_APPLICATION_CREDENTIALS` (Gmail OAuth)
