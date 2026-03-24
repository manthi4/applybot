"""Shared fixtures for discovery component tests."""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import MagicMock

import pytest

from applybot.discovery.scrapers.base import RawJob
from applybot.models.profile import UserProfile


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
