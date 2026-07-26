"""Tests for the Job model and Firestore CRUD operations (job.py)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from applybot.models.job import (
    Job,
    JobSource,
    JobStatus,
    _doc_to_job,
    _job_to_doc,
    add_job,
    add_jobs,
    count_jobs_by_status,
    get_all_job_urls,
    get_job,
    query_jobs,
    update_job,
)

# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def _make_job(**overrides: object) -> Job:
    """Create a Job with sensible defaults, applying any overrides."""
    defaults: dict[str, object] = {
        "title": "ML Engineer",
        "company": "Acme Corp",
        "location": "Remote",
        "description": "Build ML systems",
        "url": "https://example.com/job/1",
        "source": JobSource.SERPAPI,
        "status": JobStatus.NEW,
    }
    defaults.update(overrides)
    return Job(**defaults)


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------


class TestJobModel:
    def test_required_fields_set(self):
        job = Job(
            title="ML Engineer",
            company="Acme Corp",
            url="https://example.com/job/1",
            source=JobSource.SERPAPI,
        )
        assert job.title == "ML Engineer"
        assert job.company == "Acme Corp"
        assert job.url == "https://example.com/job/1"
        assert job.source == JobSource.SERPAPI

    def test_optional_defaults(self):
        job = _make_job()
        assert job.id == ""
        assert job.location == "Remote"
        assert job.status == JobStatus.NEW
        assert job.posted_date is None
        assert job.relevance_score is None
        assert job.hard_requirements == []
        assert job.application_questions == []
        assert isinstance(job.discovered_date, datetime)

    def test_repr(self):
        job = _make_job(title="Backend Eng", company="Globex")
        assert repr(job) == "<Job : Backend Eng @ Globex>"


# ---------------------------------------------------------------------------
# Serialization (_job_to_doc / _doc_to_job)
# ---------------------------------------------------------------------------


class TestJobSerialization:
    def test_enums_serialized_to_string_values(self):
        job = _make_job()
        doc = _job_to_doc(job)
        assert doc["source"] == JobSource.SERPAPI.value
        assert doc["status"] == JobStatus.NEW.value
        # id is excluded
        assert "id" not in doc

    def test_posted_date_serialized_to_iso_string(self):
        job = _make_job(posted_date=date(2025, 7, 19))
        doc = _job_to_doc(job)
        assert doc["posted_date"] == "2025-07-19"

    def test_posted_date_none_serialized_as_none(self):
        job = _make_job(posted_date=None)
        doc = _job_to_doc(job)
        assert doc["posted_date"] is None

    def test_round_trip(self):
        job = _make_job(
            posted_date=date(2025, 7, 19),
            relevance_score=0.87,
            relevance_reasoning="strong match",
            hard_requirements=["Python", "5+ years"],
            application_questions=["visa?"],
        )
        roundtripped = _doc_to_job(_StubDoc(_job_to_doc(job)))
        assert roundtripped.title == job.title
        assert roundtripped.source == job.source
        assert roundtripped.status == job.status
        assert roundtripped.posted_date == date(2025, 7, 19)
        assert roundtripped.relevance_score == 0.87
        assert roundtripped.hard_requirements == ["Python", "5+ years"]
        assert roundtripped.application_questions == ["visa?"]

    def test_discovered_date_round_trip(self):
        job = _make_job()
        ts = datetime(2025, 7, 19, 12, 0, tzinfo=UTC)
        job.discovered_date = ts
        roundtripped = _doc_to_job(_StubDoc(_job_to_doc(job)))
        # Firestore/emulator stores datetimes at microsecond precision; compare
        # at second precision to avoid float-comparison flakiness.
        assert roundtripped.discovered_date.replace(microsecond=0) == ts.replace(
            microsecond=0
        )


class _StubDoc:
    """Minimal stand-in for a Firestore DocumentSnapshot."""

    def __init__(self, data: dict[str, object]) -> None:
        self.id = str(data.get("id", "stub-id"))
        self._data = data

    def to_dict(self) -> dict[str, object]:
        return dict(self._data)


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------


class TestJobCRUD:
    def test_add_job_populates_id(self):
        job = _make_job()
        assert job.id == ""
        saved = add_job(job)
        assert saved.id != ""
        assert saved is job

    def test_get_job_existing(self):
        saved = add_job(_make_job(title="Backend Eng"))
        fetched = get_job(saved.id)
        assert fetched is not None
        assert fetched.title == "Backend Eng"
        assert fetched.source == JobSource.SERPAPI

    def test_get_job_not_found(self):
        assert get_job("nonexistent-doc-id") is None

    def test_update_job_converts_status_enum(self):
        saved = add_job(_make_job(status=JobStatus.NEW))
        update_job(saved.id, status=JobStatus.APPROVED)
        fetched = get_job(saved.id)
        assert fetched is not None
        assert fetched.status == JobStatus.APPROVED

    def test_update_job_converts_source_enum(self):
        saved = add_job(_make_job(source=JobSource.SERPAPI))
        update_job(saved.id, source=JobSource.GREENHOUSE)
        fetched = get_job(saved.id)
        assert fetched is not None
        assert fetched.source == JobSource.GREENHOUSE

    def test_update_job_partial_fields(self):
        saved = add_job(_make_job())
        update_job(saved.id, location="Berlin", relevance_score=0.91)
        fetched = get_job(saved.id)
        assert fetched is not None
        assert fetched.location == "Berlin"
        assert fetched.relevance_score == 0.91
        # Untouched fields remain
        assert fetched.title == "ML Engineer"


# ---------------------------------------------------------------------------
# Batch (add_jobs) — exercises the >400 multi-commit path
# ---------------------------------------------------------------------------


class TestJobBatch:
    def test_add_jobs_returns_count(self):
        jobs = [_make_job(url=f"https://example.com/b{i}") for i in range(5)]
        count = add_jobs(jobs)
        assert count == 5

    def test_add_jobs_populates_ids(self):
        jobs = [_make_job(url=f"https://example.com/b{i}") for i in range(3)]
        add_jobs(jobs)
        assert all(j.id != "" for j in jobs)

    def test_add_jobs_over_400_exercises_multi_commit(self, monkeypatch):
        """add_jobs must flush mid-batch at the 400-write threshold.

        The Firestore hard limit is 500 writes per batch; add_jobs commits
        every 400 writes to stay safely under it. With n=420 a correct
        implementation commits twice (once at 400, once for the remainder),
        while one that drops the mid-batch commit would commit only once and
        would silently rely on the emulator tolerating >500-write batches.
        We spy on the batch commit call count to defend the multi-commit path.
        """
        from applybot.models.base import get_db

        client = get_db()
        real_batch = type(client).batch
        commit_calls = 0

        def tracking_batch(self):
            batch = real_batch(self)
            real_commit = batch.commit

            def commit(*args, **kwargs):
                nonlocal commit_calls
                commit_calls += 1
                return real_commit(*args, **kwargs)

            batch.commit = commit  # type: ignore[method-assign]
            return batch

        monkeypatch.setattr(type(client), "batch", tracking_batch)

        n = 420
        jobs = [_make_job(url=f"https://example.com/mc{i}") for i in range(n)]
        count = add_jobs(jobs)
        assert count == n
        # Confirm they were all actually written by counting URLs.
        urls = get_all_job_urls()
        assert len(urls) == n
        # The 400-th write forces a mid-batch commit, and the remainder is
        # flushed at the end — so a correct implementation commits >= 2 times.
        assert commit_calls >= 2, f"expected multi-commit, got {commit_calls}"

    def test_add_jobs_empty(self):
        assert add_jobs([]) == 0


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


class TestJobQueries:
    def test_query_jobs_status_filter(self):
        add_job(_make_job(url="u1", status=JobStatus.NEW))
        add_job(_make_job(url="u2", status=JobStatus.APPROVED))
        add_job(_make_job(url="u3", status=JobStatus.NEW))

        results = query_jobs(status=JobStatus.NEW)
        assert len(results) == 2
        assert all(j.status == JobStatus.NEW for j in results)

    def test_query_jobs_min_score_filter(self):
        add_job(_make_job(url="u1", relevance_score=0.9))
        add_job(_make_job(url="u2", relevance_score=0.3))
        add_job(_make_job(url="u3", relevance_score=0.7))

        results = query_jobs(min_score=0.7)
        scores = sorted(
            j.relevance_score for j in results if j.relevance_score is not None
        )
        assert scores == [0.7, 0.9]

    def test_query_jobs_order_by_score_desc(self):
        add_job(_make_job(url="u1", relevance_score=0.5))
        add_job(_make_job(url="u2", relevance_score=0.95))
        add_job(_make_job(url="u3", relevance_score=0.1))

        results = query_jobs()
        scores = [j.relevance_score for j in results if j.relevance_score is not None]
        assert scores == sorted(scores, reverse=True)

    def test_query_jobs_limit(self):
        for i in range(5):
            add_job(_make_job(url=f"u{i}", relevance_score=0.1 * i))
        results = query_jobs(limit=2)
        assert len(results) == 2


# ---------------------------------------------------------------------------
# Aggregates
# ---------------------------------------------------------------------------


class TestJobAggregates:
    def test_get_all_job_urls(self):
        add_job(_make_job(url="https://a.com/1"))
        add_job(_make_job(url="https://b.com/2"))
        urls = get_all_job_urls()
        assert urls == {"https://a.com/1", "https://b.com/2"}

    def test_get_all_job_urls_empty(self):
        assert get_all_job_urls() == set()

    def test_count_jobs_by_status(self):
        add_job(_make_job(url="u1", status=JobStatus.NEW))
        add_job(_make_job(url="u2", status=JobStatus.NEW))
        add_job(_make_job(url="u3", status=JobStatus.APPROVED))

        counts = count_jobs_by_status()
        assert counts["new"] == 2
        assert counts["approved"] == 1
        assert counts["total"] == 3

    def test_count_jobs_by_status_empty(self):
        counts = count_jobs_by_status()
        assert counts == {"total": 0}
