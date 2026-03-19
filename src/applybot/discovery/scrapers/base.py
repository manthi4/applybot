"""Base scraper interface for job discovery."""

from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass
class RawJob:
    """Standard job representation returned by all scrapers."""

    title: str
    company: str
    location: str
    description: str
    url: str
    source: str
    posted_date: date | None = None
    extra: dict[str, Any] = field(default_factory=dict)


class BaseScraper(abc.ABC):
    """Abstract base class for job scrapers."""

    @property
    @abc.abstractmethod
    def source_name(self) -> str:
        """Identifier for this scraper (matches JobSource enum)."""
        ...

    @abc.abstractmethod
    async def search(
        self,
        queries: list[str],
        location: str = "",
        max_results: int = 50,
    ) -> list[RawJob]:
        """Search for jobs matching the given queries.

        Args:
            queries: Search query strings (e.g., "ML engineer robotics").
            location: Location filter (e.g., "Remote", "San Francisco").
            max_results: Maximum number of jobs to return.

        Returns:
            List of RawJob results.
        """
        ...
