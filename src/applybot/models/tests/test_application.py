"""Tests for the Application model and Firestore CRUD operations (application.py)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from applybot.models.application import (
    Application,
    ApplicationStatus,
)

APPLICATIONS_COLLECTION = "applications"


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
        doc = app.to_doc()
        assert doc["status"] == ApplicationStatus.OFFER.value
        assert type(doc["status"]) is str
        assert "id" not in doc

    def test_round_trip(self):
        app = _make_app(
            status=ApplicationStatus.SUBMITTED,
            answers={"q1": "a1", "q2": "a2"},
            profile_gaps=[{"requirement": "X"}],
        )
        roundtripped = Application.from_doc(_StubDoc(app.to_doc()))
        assert roundtripped.status == ApplicationStatus.SUBMITTED
        assert roundtripped.answers == {"q1": "a1", "q2": "a2"}
        assert roundtripped.profile_gaps == [{"requirement": "X"}]

    def test_created_at_round_trip(self):
        app = _make_app()
        ts = datetime(2025, 7, 19, 12, 0, tzinfo=UTC)
        app.created_at = ts
        roundtripped = Application.from_doc(_StubDoc(app.to_doc()))
        assert roundtripped.created_at.replace(microsecond=0) == ts.replace(
            microsecond=0
        )

    def test_submitted_at_round_trip(self):
        app = _make_app()
        ts = datetime(2025, 7, 19, 14, 30, tzinfo=UTC)
        app.submitted_at = ts
        roundtripped = Application.from_doc(_StubDoc(app.to_doc()))
        assert roundtripped.submitted_at is not None
        assert roundtripped.submitted_at.replace(microsecond=0) == ts.replace(
            microsecond=0
        )

    def test_legacy_draft_status_migrated_to_ready_for_review(self):
        """Legacy "draft" status (removed from enum) is migrated on read via from_doc."""
        stub = _StubDoc(
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
        migrated = Application.from_doc(stub)
        assert migrated.status == ApplicationStatus.READY_FOR_REVIEW


# ---------------------------------------------------------------------------
# Legacy data migration (emulator-backed)
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
        migrated = Application.get(ref.id)
        assert migrated is not None
        assert migrated.status == ApplicationStatus.READY_FOR_REVIEW


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


class TestApplicationCRUD:
    def test_save_populates_id(self):
        app = _make_app()
        assert app.id == ""
        saved = app.save()
        assert saved.id != ""
        assert saved is app

    def test_get_existing(self):
        saved = _make_app(cover_letter="Hi").save()
        fetched = Application.get(saved.id)
        assert fetched is not None
        assert fetched.cover_letter == "Hi"

    def test_get_not_found(self):
        assert Application.get("nonexistent-doc-id") is None

    def test_update_converts_status_enum(self):
        saved = _make_app(status=ApplicationStatus.READY_FOR_REVIEW).save()
        Application.update(saved.id, status=ApplicationStatus.APPROVED)
        fetched = Application.get(saved.id)
        assert fetched is not None
        assert fetched.status == ApplicationStatus.APPROVED

    def test_update_partial_fields(self):
        saved = _make_app().save()
        Application.update(saved.id, cover_letter="New letter", answers={"q": "a"})
        fetched = Application.get(saved.id)
        assert fetched is not None
        assert fetched.cover_letter == "New letter"
        assert fetched.answers == {"q": "a"}
        assert fetched.status == ApplicationStatus.READY_FOR_REVIEW  # untouched


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


class TestApplicationQueries:
    def test_query_status_filter(self):
        _make_app(job_id="j1", status=ApplicationStatus.SUBMITTED).save()
        _make_app(job_id="j2", status=ApplicationStatus.OFFER).save()
        _make_app(job_id="j3", status=ApplicationStatus.SUBMITTED).save()

        results = Application.query(status=ApplicationStatus.SUBMITTED)
        assert len(results) == 2
        assert all(a.status == ApplicationStatus.SUBMITTED for a in results)

    def test_query_ordered_by_created_at_desc(self):
        old = _make_app(job_id="old")
        old.created_at = datetime(2025, 1, 1, tzinfo=UTC)
        old.save()

        new = _make_app(job_id="new")
        new.created_at = datetime(2025, 7, 19, tzinfo=UTC)
        new.save()

        results = Application.query()
        job_ids = [a.job_id for a in results]
        assert job_ids == ["new", "old"]

    def test_query_limit(self):
        for i in range(5):
            _make_app(job_id=f"j{i}").save()
        results = Application.query(limit=2)
        assert len(results) == 2


# ---------------------------------------------------------------------------
# Aggregates
# ---------------------------------------------------------------------------


class TestApplicationAggregates:
    def test_count_by_status(self):
        _make_app(status=ApplicationStatus.SUBMITTED).save()
        _make_app(status=ApplicationStatus.SUBMITTED).save()
        _make_app(status=ApplicationStatus.OFFER).save()

        counts = Application.count_by_status()
        assert counts["submitted"] == 2
        assert counts["offer"] == 1
        assert counts["total"] == 3

    def test_count_by_status_empty(self):
        assert Application.count_by_status() == {"total": 0}


# ---------------------------------------------------------------------------
# Multi-status query
# ---------------------------------------------------------------------------


class TestApplicationsByStatuses:
    def test_in_query_matches_any_status(self):
        _make_app(job_id="j1", status=ApplicationStatus.SUBMITTED).save()
        _make_app(job_id="j2", status=ApplicationStatus.OFFER).save()
        _make_app(job_id="j3", status=ApplicationStatus.REJECTED).save()

        results = Application.by_statuses(
            [ApplicationStatus.SUBMITTED, ApplicationStatus.OFFER]
        )
        job_ids = {a.job_id for a in results}
        assert job_ids == {"j1", "j2"}

    def test_empty_statuses_returns_empty(self):
        _make_app().save()
        assert Application.by_statuses([]) == []
