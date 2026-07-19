"""Tests for the Application model and Firestore CRUD operations (application.py)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from applybot.models.application import (
    Application,
    ApplicationStatus,
    ApplicationStatusUpdate,
    UpdateSource,
    _app_to_doc,
    _doc_to_app,
    add_application,
    add_status_update,
    count_applications_by_status,
    get_application,
    get_applications_by_statuses,
    get_status_updates,
    query_applications,
    update_application,
)

APPLICATIONS_COLLECTION = "applications"
STATUS_UPDATES_COLLECTION = "application_status_updates"


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def _make_app(**overrides: Any) -> Application:
    defaults: dict[str, Any] = {
        "job_id": "job_abc",
        "cover_letter": "Dear hiring manager...",
        "answers": {"q1": "a1"},
        "profile_gaps": [{"requirement": "5 years", "have": "3 years"}],
        "status": ApplicationStatus.READY_FOR_REVIEW,
    }
    defaults.update(overrides)
    return Application(**defaults)


def _make_update(**overrides: Any) -> ApplicationStatusUpdate:
    defaults: dict[str, Any] = {
        "application_id": "app_xyz",
        "status": ApplicationStatus.APPROVED,
        "source": UpdateSource.SYSTEM,
        "details": "auto-approved",
    }
    defaults.update(overrides)
    return ApplicationStatusUpdate(**defaults)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TestApplicationModel:
    def test_defaults(self):
        app = Application(job_id="job_1")
        assert app.id == ""
        assert app.job_id == "job_1"
        assert app.status == ApplicationStatus.READY_FOR_REVIEW
        assert app.cover_letter == ""
        assert app.answers == {}
        assert app.profile_gaps == []
        assert app.submitted_at is None
        assert isinstance(app.created_at, datetime)

    def test_repr(self):
        app = _make_app()
        assert repr(app) == "<Application : job=job_abc status=ready_for_review>"


class TestStatusUpdateModel:
    def test_defaults(self):
        update = ApplicationStatusUpdate(
            application_id="app_1",
            status=ApplicationStatus.SUBMITTED,
            source=UpdateSource.MANUAL,
        )
        assert update.id == ""
        assert update.details == ""
        assert isinstance(update.timestamp, datetime)

    def test_repr(self):
        update = _make_update()
        assert repr(update) == "<StatusUpdate : approved via system>"


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


class _StubDoc:
    def __init__(self, data: dict[str, Any], doc_id: str = "stub-id") -> None:
        self.id = doc_id
        self._data = data

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)


class TestApplicationSerialization:
    def test_status_enum_serialized_to_value(self):
        app = _make_app(status=ApplicationStatus.OFFER)
        doc = _app_to_doc(app)
        assert doc["status"] == ApplicationStatus.OFFER.value
        assert "id" not in doc

    def test_round_trip(self):
        app = _make_app(
            status=ApplicationStatus.SUBMITTED,
            answers={"q1": "a1", "q2": "a2"},
            profile_gaps=[{"requirement": "X"}],
        )
        roundtripped = _doc_to_app(_StubDoc(_app_to_doc(app)))
        assert roundtripped.status == ApplicationStatus.SUBMITTED
        assert roundtripped.answers == {"q1": "a1", "q2": "a2"}
        assert roundtripped.profile_gaps == [{"requirement": "X"}]

    def test_created_at_round_trip(self):
        app = _make_app()
        ts = datetime(2025, 7, 19, 12, 0, tzinfo=UTC)
        app.created_at = ts
        roundtripped = _doc_to_app(_StubDoc(_app_to_doc(app)))
        assert roundtripped.created_at.replace(microsecond=0) == ts.replace(
            microsecond=0
        )

    def test_submitted_at_round_trip(self):
        app = _make_app()
        ts = datetime(2025, 7, 19, 14, 30, tzinfo=UTC)
        app.submitted_at = ts
        roundtripped = _doc_to_app(_StubDoc(_app_to_doc(app)))
        assert roundtripped.submitted_at is not None
        assert roundtripped.submitted_at.replace(microsecond=0) == ts.replace(
            microsecond=0
        )


# ---------------------------------------------------------------------------
# Legacy data migration
# ---------------------------------------------------------------------------


class TestApplicationLegacyMigration:
    def test_legacy_draft_status_migrated_to_ready_for_review(self, db_client):
        """Legacy "draft" status (removed from enum) is migrated on read.

        Uses raw dict injection per firestore_emulator.md's "Bypass Pydantic for
        Legacy Data Tests" rule.
        """
        _, ref = db_client.collection(APPLICATIONS_COLLECTION).add(
            {
                "job_id": "job_legacy",
                "status": "draft",
                "cover_letter": "",
                "answers": {},
                "profile_gaps": [],
                "created_at": datetime.now(UTC),
                "submitted_at": None,
            }
        )
        migrated = get_application(ref.id)
        assert migrated is not None
        assert migrated.status == ApplicationStatus.READY_FOR_REVIEW


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


class TestApplicationCRUD:
    def test_add_application_populates_id(self):
        app = _make_app()
        assert app.id == ""
        saved = add_application(app)
        assert saved.id != ""
        assert saved is app

    def test_get_application_existing(self):
        saved = add_application(_make_app(cover_letter="Hi"))
        fetched = get_application(saved.id)
        assert fetched is not None
        assert fetched.cover_letter == "Hi"

    def test_get_application_not_found(self):
        assert get_application("nonexistent-doc-id") is None

    def test_update_application_converts_status_enum(self):
        saved = add_application(_make_app(status=ApplicationStatus.READY_FOR_REVIEW))
        update_application(saved.id, status=ApplicationStatus.APPROVED)
        fetched = get_application(saved.id)
        assert fetched is not None
        assert fetched.status == ApplicationStatus.APPROVED

    def test_update_application_partial_fields(self):
        saved = add_application(_make_app())
        update_application(saved.id, cover_letter="New letter", answers={"q": "a"})
        fetched = get_application(saved.id)
        assert fetched is not None
        assert fetched.cover_letter == "New letter"
        assert fetched.answers == {"q": "a"}
        assert fetched.status == ApplicationStatus.READY_FOR_REVIEW  # untouched


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


class TestApplicationQueries:
    def test_query_applications_status_filter(self):
        add_application(_make_app(job_id="j1", status=ApplicationStatus.SUBMITTED))
        add_application(_make_app(job_id="j2", status=ApplicationStatus.OFFER))
        add_application(_make_app(job_id="j3", status=ApplicationStatus.SUBMITTED))

        results = query_applications(status=ApplicationStatus.SUBMITTED)
        assert len(results) == 2
        assert all(a.status == ApplicationStatus.SUBMITTED for a in results)

    def test_query_applications_ordered_by_created_at_desc(self):
        old = _make_app(job_id="old")
        old.created_at = datetime(2025, 1, 1, tzinfo=UTC)
        add_application(old)

        new = _make_app(job_id="new")
        new.created_at = datetime(2025, 7, 19, tzinfo=UTC)
        add_application(new)

        results = query_applications()
        job_ids = [a.job_id for a in results]
        assert job_ids == ["new", "old"]

    def test_query_applications_limit(self):
        for i in range(5):
            add_application(_make_app(job_id=f"j{i}"))
        results = query_applications(limit=2)
        assert len(results) == 2


# ---------------------------------------------------------------------------
# Aggregates
# ---------------------------------------------------------------------------


class TestApplicationAggregates:
    def test_count_applications_by_status(self):
        add_application(_make_app(status=ApplicationStatus.SUBMITTED))
        add_application(_make_app(status=ApplicationStatus.SUBMITTED))
        add_application(_make_app(status=ApplicationStatus.OFFER))

        counts = count_applications_by_status()
        assert counts["submitted"] == 2
        assert counts["offer"] == 1
        assert counts["total"] == 3

    def test_count_applications_by_status_empty(self):
        assert count_applications_by_status() == {"total": 0}


# ---------------------------------------------------------------------------
# Status updates (audit trail)
# ---------------------------------------------------------------------------


class TestStatusUpdates:
    def test_add_status_update_populates_id(self):
        update = _make_update()
        assert update.id == ""
        saved = add_status_update(update)
        assert saved.id != ""

    def test_get_status_updates_filtered_by_application(self):
        app_a = add_application(_make_app())
        app_b = add_application(_make_app())

        add_status_update(
            _make_update(application_id=app_a.id, status=ApplicationStatus.APPROVED)
        )
        add_status_update(
            _make_update(application_id=app_b.id, status=ApplicationStatus.REJECTED)
        )

        results = get_status_updates(app_a.id)
        assert len(results) == 1
        assert results[0].status == ApplicationStatus.APPROVED

    def test_get_status_updates_ordered_by_timestamp(self):
        app = add_application(_make_app())
        early = _make_update(application_id=app.id, status=ApplicationStatus.APPROVED)
        early.timestamp = datetime(2025, 1, 1, 12, 0, tzinfo=UTC)
        late = _make_update(application_id=app.id, status=ApplicationStatus.INTERVIEW)
        late.timestamp = datetime(2025, 6, 1, 12, 0, tzinfo=UTC)

        add_status_update(early)
        add_status_update(late)

        results = get_status_updates(app.id)
        assert [r.status for r in results] == [
            ApplicationStatus.APPROVED,
            ApplicationStatus.INTERVIEW,
        ]


# ---------------------------------------------------------------------------
# Multi-status query
# ---------------------------------------------------------------------------


class TestApplicationsByStatuses:
    def test_in_query_matches_any_status(self):
        add_application(_make_app(job_id="j1", status=ApplicationStatus.SUBMITTED))
        add_application(_make_app(job_id="j2", status=ApplicationStatus.OFFER))
        add_application(_make_app(job_id="j3", status=ApplicationStatus.REJECTED))

        results = get_applications_by_statuses(
            [ApplicationStatus.SUBMITTED, ApplicationStatus.OFFER]
        )
        job_ids = {a.job_id for a in results}
        assert job_ids == {"j1", "j2"}

    def test_empty_statuses_returns_empty(self):
        add_application(_make_app())
        assert get_applications_by_statuses([]) == []
