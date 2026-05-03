# Models

Pydantic data models and Firestore CRUD functions. This is the foundational data layer — all other components depend on these models.

## Files

- **base.py** — Firestore client singleton (`get_db()`, `init_db()`)
- **job.py** — `Job` model and CRUD functions for job listings
- **profile.py** — `UserProfile` model with singleton document pattern
- **application.py** — `Application`, `ApplicationStatusUpdate` models and CRUD functions

## Public API

### Database Setup

```python
from applybot.models.base import get_db, init_db

init_db()              # Verify Firestore connection (no schema needed)
db = get_db()          # Get Firestore Client singleton
```

### Enums

```python
from applybot.models.job import JobStatus, JobSource
# JobStatus: NEW, REVIEWING, APPROVED, SKIPPED, APPLIED, REJECTED
# JobSource: SERPAPI, GREENHOUSE, LEVER, EU_REMOTE_JOBS, MANUAL

from applybot.models.application import ApplicationStatus, UpdateSource
# ApplicationStatus: DRAFT → READY_FOR_REVIEW → APPROVED → SUBMITTED → RECEIVED → INTERVIEW → OFFER / REJECTED / WITHDRAWN
# UpdateSource: MANUAL, GMAIL, SYSTEM
```

### Pydantic Models

| Model | Key Fields | Firestore Collection |
|---|---|---|
| `Job` | id, title, company, location, description, url, source, posted_date, relevance_score, status | `jobs` |
| `ContactInfo` | email, linkedin, phone, github | (nested in `UserProfile`) |
| `UserProfile` | name, contact_info, summary, skills, experiences, education, preferences, resume_path | `profiles` (singleton doc `"default"`) |
| `Application` | id, job_id, tailored_resume_path, cover_letter, answers, status, submitted_at | `applications` |
| `ApplicationStatusUpdate` | id, application_id, status, source, details, timestamp | `application_status_updates` |

### CRUD Functions

**Jobs** (`job.py`):
- `get_job(job_id: str) -> Job | None`
- `add_job(job: Job) -> str` — returns generated doc ID
- `add_jobs(jobs: list[Job]) -> int` — batch write, returns count
- `update_job(job_id: str, **fields) -> None`
- `query_jobs(status, min_score, limit) -> list[Job]`
- `get_all_job_urls() -> set[str]`
- `count_jobs_by_status() -> dict[str, int]`

**Applications** (`application.py`):
- `get_application(app_id: str) -> Application | None`
- `add_application(app: Application) -> str`
- `update_application(app_id: str, **fields) -> None`
- `query_applications(status, limit) -> list[Application]`
- `count_applications_by_status() -> dict[str, int]`
- `add_status_update(update: ApplicationStatusUpdate) -> str`
- `get_status_updates(app_id: str) -> list[ApplicationStatusUpdate]`
- `get_applications_by_statuses(statuses) -> list[Application]`

**Profile** (`profile.py`):
- `get_profile() -> UserProfile | None`
- `save_profile(profile: UserProfile) -> None`
- `update_profile_fields(**fields) -> None`
- `delete_profile() -> None`

## Boundaries

- **No business logic** — models define data shapes and CRUD only
- **No direct imports from other applybot modules** — this is a leaf dependency
- All IDs are `str` (Firestore document IDs)
- Database connection configured via `settings.gcp_project_id` (falls back to Application Default Credentials)
