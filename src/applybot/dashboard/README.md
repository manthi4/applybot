# Dashboard

Central web interface for monitoring and controlling ApplyBot. Consists of a FastAPI REST backend and a Streamlit frontend.

## Files

- **api.py** — FastAPI application with REST endpoints
- **frontend.py** — Streamlit multi-page app

## REST API

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/jobs` | List jobs (filter: `status`, `min_score`; `limit` ≤ 500) |
| GET | `/jobs/{job_id}` | Job details |
| POST | `/jobs/{job_id}/approve` | Mark job as APPROVED |
| POST | `/jobs/{job_id}/skip` | Mark job as SKIPPED |
| GET | `/applications` | List applications (filter: `status`; `limit` ≤ 500) |
| GET | `/applications/{app_id}` | Application details |
| POST | `/applications/{app_id}/review` | Update application status (body: `{"action": "approve"}`) |
| GET | `/profile` | Current user profile |
| PUT | `/profile` | Update profile fields |
| GET | `/dashboard/summary` | Counts by status for jobs and applications |

### Response Models

- `JobOut` — job fields + relevance_score + status
- `ApplicationOut` — application fields + nested job + status history
- `ProfileOut` — profile fields
- `DashboardSummary` — `{jobs_by_status: {...}, applications_by_status: {...}}`

### Running the API

```python
import uvicorn
from applybot.dashboard.api import app

uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Streamlit Frontend

Pages:
1. **Overview** — Stats cards, pipeline visualization, application status charts
2. **Job Queue** — Filterable job list with approve/skip actions
3. **Applications** — Applications by status with cover letter, answers, and review actions
4. **Profile** — Name/email/summary editor + full profile data export

The frontend communicates with the FastAPI backend via HTTP (`httpx`, 20s timeout).

### Running the Frontend

```bash
streamlit run src/applybot/dashboard/frontend.py
```

## Boundaries

- **Depends on**: `models` (all ORM models for DB queries), `config` (database URL)
- **Does not depend on**: LLM, Discovery, Application, Tracking, or Profile *directly* — reads/writes DB only
- **Used by**: End users via browser, potentially other services via REST API
- The API is read-heavy; write operations are limited to status changes and profile updates
- The frontend is a thin UI layer — all business logic lives in the API and underlying modules
