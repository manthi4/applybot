# Tracking

Manages the application lifecycle through a validated state machine and integrates with Gmail to auto-detect status updates from emails.

## Files

- **tracker.py** — `ApplicationTracker` — state machine with enforced transitions, queries, and summaries
- **gmail.py** — `scan_gmail_for_updates()` — scans emails, classifies with Claude, and updates application status

## Public API

### Tracker

```python
from applybot.tracking.tracker import ApplicationTracker

tracker = ApplicationTracker()

# Update application status (validates transition)
app = tracker.update_status(app_id, ApplicationStatus.SUBMITTED, source=UpdateSource.MANUAL, details="...")
# Raises InvalidTransitionError if transition is not allowed

# Query applications
apps = tracker.get_applications(status=ApplicationStatus.SUBMITTED, limit=50)

# Summary counts by status
summary: dict[str, int] = tracker.get_summary()
```

### Valid State Transitions

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

### Gmail Integration

```python
from applybot.tracking.gmail import scan_gmail_for_updates

updates: list[dict] = scan_gmail_for_updates()
# Scans for emails from applied-to companies (last 3 days)
# Classifies via Claude (confidence ≥ 0.7 → auto-update)
# Returns list of status changes made
```

Email classification maps to: `received`, `rejected`, `interview`, `offer`.

## Boundaries

- **Depends on**: `models` (Application, ApplicationStatus, ApplicationStatusUpdate ORM), `llm` (Gmail email classification), `config` (Google credentials)
- **Does not depend on**: Discovery, Application (prep), Profile, or Dashboard
- **Used by**: Dashboard (displays status), CLI/scheduler entry points
- Gmail integration requires Google OAuth2 credentials (setup not yet automated)
- The tracker owns all status transitions — other components must go through `update_status()` to change application state
