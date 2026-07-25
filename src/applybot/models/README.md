# Models

Pydantic data models and Firestore CRUD functions. This is the foundational data layer — all other components depend on these models.
- **No business logic** — models define data shapes and CRUD only
- **No direct imports from other applybot modules** — this is a leaf dependency
- Database connection configured via `settings.gcp_project_id` (falls back to Application Default Credentials)

## File Structure
```
models/
├── application.py      # `Application`, `ApplicationStatusUpdate` models and CRUD functions
├── base.py             # Firestore client singleton (`get_db()`, `init_db()`)
├── job.py              # `Job` model and CRUD functions for job listings
├── profile.py          # `UserProfile` model with singleton document pattern
├── requirements.in     # runtime deps for this module (mirrors root pyproject.toml)
├── requirements-dev.in # dev/test deps for this module (mirrors root pyproject.toml)
└── tests/              # pytest suite — runs against a local Firestore emulator
    ├── conftest.py             # sets FIRESTORE_EMULATOR_HOST, skips when unreachable
    ├── firestore_emulator.md   # how to start the emulator
    ├── test_application.py
    ├── test_base.py
    ├── test_job.py
    └── test_profile.py
```

## Testing

The model tests exercise real Firestore reads/writes against a **local Firestore
emulator** — no Google Cloud traffic, no cloud cost. They live in `tests/` and
are collected by pytest via the `testpaths = ["tests", "src"]` setting in the
root `pyproject.toml`.

### Running the tests

```bash
# 1. Install dev dependencies (once)
pip install -e ".[dev]"

# 2. Start the Firestore emulator on localhost:8080
docker run -d --name firestore-emulator -p 8080:8080 \
  google/cloud-sdk:latest \
  gcloud beta emulators firestore start --host-port=0.0.0.0:8080

# 3. Run the model tests
pytest src/applybot/models/tests/ -v
```

To reuse the emulator on subsequent runs (it persists as a named container):

```bash
docker start firestore-emulator   # already created — just start it
docker stop firestore-emulator    # stop it when done
```

For alternative ways to run the emulator (Firebase CLI, native `gcloud`), see
[`tests/firestore_emulator.md`](./tests/firestore_emulator.md).

### ARM64 hosts (Apple Silicon, WSL2 on ARM)

`google/cloud-sdk:latest` publishes an **amd64-only** image. On an arm64 host
the container exits with `exec /usr/bin/gcloud: exec format error`. Register
QEMU user emulation **once** — the registration persists across reboots:

```bash
docker run --privileged --rm tonistiigi/binfmt --install amd64
```

After that, the `docker run` command above works unchanged (the amd64 image
runs under emulation). The emulator is a small Java process; the emulation
overhead is negligible for the test suite.

### Test configuration & skip behavior

The suite is configured in `tests/conftest.py`:

- **Emulator routing:** `FIRESTORE_EMULATOR_HOST=localhost:8080` and
  `GOOGLE_CLOUD_PROJECT=applybot-test` are set before any `applybot` or
  `google.cloud` code is imported, so the lazy Firestore singleton in
  `base.py` routes all traffic to the emulator with no patching required.
- **Per-test isolation:** an autouse `clear_emulator` fixture wipes every
  collection via the emulator's admin REST API after each test, so every test
  starts from an empty database.
- **Skip-when-unreachable:** if the emulator is not reachable at
  `localhost:8080` (or `google-cloud-firestore`/`grpcio` can't be imported),
  every test in this folder is **skipped**, not errored. This keeps the suite
  green on machines without the emulator.

So a result of **`N skipped`** means the emulator wasn't running — start it
and re-run. A result of **`N passed`** means the tests actually executed
against the emulator.

### Pre-commit hooks

These tests are **not** part of the pre-commit hooks. `.pre-commit-config.yaml`
runs only static checks (trailing-whitespace, end-of-file-fixer, yaml/json/toml
validators, `black`, `ruff --fix`, `mypy`) — no `pytest` hook. This is
intentional: requiring every contributor to run a Java-based emulator on every
commit would be slow and brittle. Run the model tests manually (as above) or
via CI before merging.
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
- All IDs are `str` (Firestore document IDs)


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


### Profile (`profile/`)

**ProfileManager** — CRUD operations for the UserProfile table:
- `get_profile()`, `get_or_create_profile(name, email)`, `update_profile(**kwargs)`
- `get_skills()`, `export_profile_json(path)`, `import_profile_json(path)`

**Resume** — .docx parsing and generation:
- `parse_resume(path)` → `ResumeData` (name, contact_info, sections with title + content)
- `generate_resume(data, template_path, output_path)` → creates tailored .docx preserving template formatting

**Bootstrap flow** (planned): On first run, parse existing resume → extract structured profile → store in DB → agent identifies gaps → interactive CLI to fill them in.
