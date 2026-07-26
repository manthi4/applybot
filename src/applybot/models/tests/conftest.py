"""Pytest fixtures for Firestore emulator-backed model tests.

Sets up a real ``google-cloud-firestore`` client pointed at a local Firestore
emulator (no Google Cloud traffic).  See ``firestore_emulator.md`` for how to
start the emulator.

If the emulator is not running (or the firestore client / grpcio cannot be
imported), every test in this folder is skipped rather than errored, so the
suite stays green on machines without the emulator.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

# Route the Firestore client at the emulator *before* any applybot code or the
# firestore client is imported.  Setting these here means the lazy singleton in
# applybot.models.base will talk to the emulator with no further patching.
os.environ["FIRESTORE_EMULATOR_HOST"] = "localhost:8080"
os.environ["GOOGLE_CLOUD_PROJECT"] = "applybot-test"

import pytest  # noqa: E402

EMULATOR_HOST = os.environ["FIRESTORE_EMULATOR_HOST"]
PROJECT_ID = os.environ["GOOGLE_CLOUD_PROJECT"]
# Base REST endpoint used by the emulator's admin API (for wiping state).
CLEAR_URL = (
    f"http://{EMULATOR_HOST}/emulator/v1/"
    f"projects/{PROJECT_ID}/databases/(default)/documents"
)


def _emulator_reachable() -> bool:
    """Return True if the emulator REST endpoint responds."""
    import urllib.error
    import urllib.request

    try:
        # A GET on the emulator root returns 200 when the emulator is up. The
        # documents endpoint (CLEAR_URL) returns 404 on an empty database, so it
        # is NOT a usable health check — only the root is.
        urllib.request.urlopen(f"http://{EMULATOR_HOST}/", timeout=1).read()
    except (urllib.error.URLError, OSError, TimeoutError):
        return False
    return True


# Attempt to import the real firestore client; if grpcio / the client cannot be
# imported on this platform, we skip the whole folder rather than erroring.
try:
    from google.cloud import firestore  # noqa: F401

    _FIRESTORE_IMPORTABLE = True
    _IMPORT_ERROR: str | None = None
except Exception as exc:  # pragma: no cover - environment-dependent
    _FIRESTORE_IMPORTABLE = False
    _IMPORT_ERROR = f"{type(exc).__name__}: {exc}"


@pytest.fixture(scope="session")
def emulator_available() -> None:
    """Skip the session if the emulator is not running or firestore can't import."""
    if not _FIRESTORE_IMPORTABLE:
        pytest.skip(
            f"google-cloud-firestore could not be imported: {_IMPORT_ERROR}",
            allow_module_level=True,
        )
    if not _emulator_reachable():
        pytest.skip(
            f"Firestore emulator not reachable at {EMULATOR_HOST}. "
            "Start it with: docker run -d -p 8080:8080 google/cloud-sdk:latest "
            "gcloud beta emulators firestore start --host-port=0.0.0.0:8080",
            allow_module_level=True,
        )


@pytest.fixture(scope="session")
def db_client(emulator_available) -> firestore.Client:
    """A persistent Firestore client for the test session.

    Because ``FIRESTORE_EMULATOR_HOST`` is set, this client routes all traffic
    to the local emulator automatically.
    """
    return firestore.Client(project=PROJECT_ID)


def _wipe_emulator() -> None:
    """Best-effort DELETE of all documents in the emulator.

    A single DELETE on the documents root clears every collection.  Failures
    are logged but never raised, so a wipe problem surfaces as diagnosable
    cross-test contamination rather than aborting the run.
    """
    import urllib.request

    try:
        urllib.request.urlopen(
            urllib.request.Request(CLEAR_URL, method="DELETE"), timeout=5
        ).read()
    except Exception as exc:
        logger.warning(
            "Failed to wipe Firestore emulator at %s: %s: %s",
            CLEAR_URL,
            type(exc).__name__,
            exc,
        )


@pytest.fixture(autouse=True)
def clear_emulator(emulator_available) -> None:
    """Wipe every collection in the emulator before and after each test.

    Wiping before the test guarantees a clean start even when a single test
    is run in isolation against an emulator carrying leftover data.  Wiping
    after keeps the run tidy for the next test.  Both wipes are best-effort;
    failures are logged (see ``_wipe_emulator``) but never fail the run.
    """
    _wipe_emulator()
    yield
    _wipe_emulator()
