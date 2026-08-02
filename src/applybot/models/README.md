# Models

Pydantic data models and Firestore CRUD functions. This is the foundational data layer — all other components depend on these models.
- **No business logic** — models define data shapes and CRUD only
- **No direct imports from other applybot modules** — this is a leaf dependency
- Database connection configured via `settings.gcp_project_id` (falls back to Application Default Credentials)

## File Structure
```
models/
├── application.py      # `Application` model (inherits `FirestoreModel`) + `ApplicationStatus` enum
├── base.py             # Firestore client (`lru_cache` singleton: `get_db`, `init_db`) + `FirestoreModel` base class
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

`Job` and `Application` inherit from `FirestoreModel` (in `base.py`), which
provides document-level CRUD (`get`/`save`/`update`/`count_by_status`) against
a single auto-ID Firestore collection. `UserProfile` is a standalone
`pydantic.BaseModel` — its singleton-document pattern (fixed id `"default"`,
replace-on-save) does not fit the auto-ID collection shape, so it keeps its own
classmethods.

### Database Setup

```python
from applybot.models.base import get_db, init_db

init_db()              # Eagerly construct the Firestore client (no network round-trip)
db = get_db()          # Cached client singleton (functools.lru_cache, maxsize=1)
# To force re-init (e.g. in tests): get_db.cache_clear()
```

`get_db()` reads `FIRESTORE_EMULATOR_HOST`/`GOOGLE_CLOUD_PROJECT` from the
environment (test suite) and falls back to Application Default Credentials
otherwise. The client is cached for the process lifetime.

### Enums

```python
from applybot.models.job import JobStatus, JobSource
# JobStatus: NEW, REVIEWING, APPROVED, SKIPPED, APPLIED, REJECTED
# JobSource: SERPAPI, GREENHOUSE, LEVER, EU_REMOTE_JOBS, MANUAL

from applybot.models.application import ApplicationStatus
# ApplicationStatus: READY_FOR_REVIEW, APPROVED, SUBMITTED, RECEIVED,
#                    INTERVIEW, OFFER, REJECTED, WITHDRAWN
```

### Pydantic Models
- All IDs are `str` (Firestore document IDs)


| Model | Key Fields | Firestore Collection |
|---|---|---|
| `FirestoreModel` | id | (base class — `COLLECTION` set by subclasses) |
| `Job` | id, title, company, location, description, url, source, posted_date, discovered_date, relevance_score, status, hard_requirements, application_questions | `jobs` |
| `ContactInfo` | email, linkedin, phone, github | (nested in `UserProfile`) |
| `UserProfile` | id, name, contact_info, summary, skills, experiences, education, preferences, resume_path, updated_at | `profiles` (singleton doc `"default"`) |
| `Application` | id, job_id, tailored_resume_path, cover_letter, answers, profile_gaps, status, created_at, submitted_at | `applications` |

### CRUD API

All access is via classmethods on the models (no module-level CRUD functions).

**`FirestoreModel`** (base, `base.py`) — inherited by `Job` and `Application`:
- `FirestoreModel.get(doc_id) -> Self | None` — fetch by id
- `instance.save() -> Self` — insert (auto-generated id), populate `self.id`
- `FirestoreModel.update(doc_id, **fields) -> None` — patch fields
- `FirestoreModel.count_by_status() -> dict[str, int]` — tally by `status` + `total`
- `instance.to_doc() -> dict` / `cls.from_doc(doc) -> Self` — (de)serialization hooks

**`Job`** (`job.py`) — inherits `FirestoreModel`, plus:
- `Job.get(doc_id)`, `job.save()`, `Job.update(doc_id, **fields)`, `Job.count_by_status()`
- `Job.query(*, status=None, min_score=None, limit=100) -> list[Job]` — ordered by `relevance_score` DESC
- `Job.add_many(jobs: list[Job]) -> int` — batch write, returns count (mutates each `.id`)
- `Job.all_urls() -> set[str]` — all existing URLs (for dedup)

**`Application`** (`application.py`) — inherits `FirestoreModel`, plus:
- `Application.get(doc_id)`, `app.save()`, `Application.update(doc_id, **fields)`, `Application.count_by_status()`
- `Application.query(*, status=None, limit=100) -> list[Application]` — ordered by `created_at` DESC
- `Application.by_statuses(statuses: list[ApplicationStatus]) -> list[Application]` — `in` filter
- `Application.from_doc` migrates the legacy `"draft"` status to `READY_FOR_REVIEW` on read

**`UserProfile`** (`profile.py`) — standalone `BaseModel` (singleton):
- `UserProfile.get() -> UserProfile | None` — read the singleton doc
- `profile.save() -> UserProfile` — create or fully replace (sets `updated_at`, `id = "default"`)
- `UserProfile.update(**fields) -> UserProfile` — patch fields (raises `ValueError` if no profile exists)
- `UserProfile.delete() -> None`


### Profile (`profile/`)

**Resume** — .docx parsing and generation:
- `parse_resume(path)` → `ResumeData` (name, contact_info, sections with title + content)
- `generate_resume(data, template_path, output_path)` → creates tailored .docx preserving template formatting

**Bootstrap flow** (planned): On first run, parse existing resume → extract structured profile → store in DB
