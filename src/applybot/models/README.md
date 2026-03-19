# Models

Shared SQLAlchemy ORM models and database session management. This is the foundational data layer — all other components depend on these models.

## Files

- **base.py** — Engine creation, session factory, `Base` declarative base
- **job.py** — `Job` model for discovered job listings
- **profile.py** — `UserProfile` model with JSON columns for structured data
- **application.py** — `Application` model, status updates, and audit trail

## Public API

### Database Setup

```python
from applybot.models.base import get_session, init_db

init_db()                  # Create all tables (dev only; use Alembic in prod)
session = get_session()    # Get a new SQLAlchemy Session
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

### ORM Models

| Model | Key Columns | Relationships |
|---|---|---|
| `Job` | title, company, location, description, url, source, posted_date, relevance_score, status | → Application |
| `UserProfile` | name, email, summary, skills (JSON), experiences (JSON), education (JSON), preferences (JSON), resume_path | — |
| `Application` | job_id (FK), tailored_resume_path, cover_letter, answers (JSON), status, submitted_at | → Job, → ApplicationStatusUpdate |
| `ApplicationStatusUpdate` | application_id (FK), status, source, details, timestamp | → Application |

## Boundaries

- **No business logic** — models define schema and relationships only
- **No direct imports from other applybot modules** — this is a leaf dependency
- Consumers create their own sessions via `get_session()` and manage transactions
- Database URL configured via `settings.database_url` (defaults to `sqlite:///data/applybot.db`)
