"""Shared fixtures for discovery component tests."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock as _MagicMock

# Inject mock google.cloud.firestore_v1 into sys.modules so tests can run
# without the real google-cloud-firestore package (e.g. Windows ARM64).
_mock_base_query = _MagicMock()
_mock_firestore_v1 = _MagicMock()
_mock_firestore_v1.base_query = _mock_base_query
sys.modules.setdefault("google", _MagicMock())
sys.modules.setdefault("google.cloud", _MagicMock())
sys.modules.setdefault("google.cloud.firestore_v1", _mock_firestore_v1)
sys.modules.setdefault("google.cloud.firestore_v1.base_query", _mock_base_query)

from datetime import date  # noqa: E402
from typing import Any  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402

import pytest  # noqa: E402

from applybot.discovery.scrapers.base import RawJob  # noqa: E402
from applybot.models.profile import UserProfile  # noqa: E402


def make_raw_job(
    title: str = "ML Engineer",
    company: str = "Acme Corp",
    location: str = "Remote",
    description: str = "Build ML systems",
    url: str = "https://example.com/job/1",
    source: str = "test",
    posted_date: date | None = None,
    extra: dict[str, Any] | None = None,
) -> RawJob:
    """Factory for creating RawJob instances in tests."""
    return RawJob(
        title=title,
        company=company,
        location=location,
        description=description,
        url=url,
        source=source,
        posted_date=posted_date,
        extra=extra or {},
    )


@pytest.fixture()
def sample_jobs() -> list[RawJob]:
    """A small set of distinct jobs for general testing."""
    return [
        make_raw_job(
            title="ML Engineer",
            company="Acme Corp",
            url="https://acme.com/jobs/1",
            description="Deep learning and robotics",
        ),
        make_raw_job(
            title="Data Scientist",
            company="Beta Inc",
            url="https://beta.com/jobs/2",
            description="Statistical modeling and analytics",
        ),
        make_raw_job(
            title="Robotics Software Engineer",
            company="Gamma Robotics",
            url="https://gamma.com/jobs/3",
            description="ROS and motion planning",
        ),
    ]


@pytest.fixture()
def mock_profile() -> UserProfile:
    """A mock UserProfile (not persisted to DB) for testing LLM interactions."""
    profile = MagicMock(spec=UserProfile)
    profile.name = "Test User"
    profile.summary = "ML engineer with 5 years robotics experience"
    profile.skills = {
        "technical": ["Python", "PyTorch", "ROS", "C++", "deep learning"],
    }
    profile.experiences = [
        {
            "title": "ML Engineer",
            "company": "RoboTech",
            "summary": "Built perception models for autonomous robots",
        },
        {
            "title": "Research Intern",
            "company": "University Lab",
            "summary": "Published papers on reinforcement learning",
        },
    ]
    profile.preferences = {
        "locations": ["Remote", "San Francisco"],
        "min_salary": 120000,
    }
    profile.email = "test@example.com"
    return profile
