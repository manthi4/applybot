# ApplyBot Firestore Testing Guide

This document outlines the standard operating procedure for testing ApplyBot's Firestore data models. It is intended for both human developers and autonomous coding agents to ensure a deterministic, isolated testing environment.

## 1. Core Principle: Never Test in Production

To prevent accidental data corruption and avoid unnecessary cloud costs, all tests must run against a local Firestore Emulator.

The Python client library (`google-cloud-firestore`) will automatically route all traffic to the emulator if the `FIRESTORE_EMULATOR_HOST` environment variable is set.

## 2. Starting the Emulator

Google provides two different ways to run the emulator depending on your toolchain. You only need to run one of these options before executing the test suite.

### Option A: Standalone Emulator (Docker / gcloud)

Best for pure backend Python environments. Does not require Node.js or a Firebase project. Using Docker guarantees a clean, ephemeral environment.

```bash
# Run via Docker (Recommended for Agents)
docker run -d -p 8080:8080 google/cloud-sdk:latest \
  gcloud beta emulators firestore start --host-port=0.0.0.0:8080
```

If you have the Google Cloud CLI installed locally, you can run:

```bash
gcloud emulators firestore start --host-port=127.0.0.1:8080
```

_Source: [Google Cloud: Use Firestore emulator locally](https://cloud.google.com/firestore/docs/emulator)_

### Option B: Firebase Local Emulator Suite (Firebase CLI)

Best if you also want a visual web UI, or if you are testing Firebase Security Rules. Requires Node.js and the `firebase-tools` npm package.

```bash
# Start the Firestore emulator specifically
firebase emulators:start --only firestore
```

_Sources:_

- _[Firebase: Install and configure Emulator Suite](https://firebase.google.com/docs/emulator-suite/install_configure)_
- _[Firebase: Test Security Rules with the Emulator](https://firebase.google.com/docs/rules/rules-test-emulator)_

## 3. Test Configuration (`conftest.py`)

The test suite relies on pytest fixtures located in `tests/conftest.py` to enforce the emulator connection and reset state between tests.

### Required Fixtures

When configuring or updating `conftest.py`, ensure the following elements are present:

- **Environment Override:** `FIRESTORE_EMULATOR_HOST` must be set before the Firestore client is initialized.
- **Dependency Injection:** The `get_db()` function must be patched exactly where it is used (`applybot.models.applications`), not where it is defined (`applybot.models.base`).
- **State Teardown:** The emulator must be wiped clean after every test using its REST API.

```python
# tests/conftest.py
import os
import requests
import pytest
from unittest.mock import patch
from google.cloud import firestore

# 1. Force emulator routing (Matches default port 8080 for both gcloud and firebase CLIs)
os.environ["FIRESTORE_EMULATOR_HOST"] = "localhost:8080"
os.environ["GOOGLE_CLOUD_PROJECT"] = "applybot-test"


@pytest.fixture(scope="session")
def db_client():
    """Provides a persistent client for the test session."""
    return firestore.Client(project="applybot-test")


@pytest.fixture(autouse=True)
def mock_get_db(db_client):
    """Hooks into the application's DB getter to use the test client."""
    # NOTE: We patch where get_db is imported/used, not where it is defined.
    with patch("applybot.models.applications.get_db", return_value=db_client):
        yield db_client


@pytest.fixture(autouse=True)
def clear_emulator():
    """Wipes the emulator database after every test run."""
    yield
    project_id = os.environ["GOOGLE_CLOUD_PROJECT"]
    url = f"http://localhost:8080/emulator/v1/projects/{project_id}/databases/(default)/documents"
    requests.delete(url)
```

## 4. Writing Tests

When writing or modifying tests, adhere to the following rules:

- **Assume an Empty Database:** Because of the `clear_emulator` fixture, every test starts with 0 documents. You must seed any necessary state in the _Given_ phase of your test.
- **Test Serialization Boundaries:** Pydantic models (like `Application`) and Firestore documents are distinct. Always verify that `Enum`s and `Datetime`s correctly convert to strings/timestamps when passing through `_app_to_doc` and `_doc_to_app`.
- **Bypass Pydantic for Legacy Data Tests:** If testing migration logic (e.g., handling deprecated statuses like `"draft"`), inject raw dictionaries directly into Firestore using the `db_client` fixture, rather than using the application's `add_application` function.

### Example Test Structure

```python
def test_create_and_fetch_application(db_client):
    # 1. Given (Seed data)
    from applybot.models.applications import Application, add_application, get_application
    app = Application(job_id="job_abc")

    # 2. When (Action)
    saved_app = add_application(app)

    # 3. Then (Assertion)
    fetched_app = get_application(saved_app.id)
    assert fetched_app.job_id == "job_abc"
```
