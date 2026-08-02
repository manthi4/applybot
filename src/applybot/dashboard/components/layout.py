"""Layout components for the ApplyBot dashboard (nav, page, alert)."""

from __future__ import annotations

import logging

from fasthtml.common import (
    A,
    Article,
    Button,
    Container,
    Form,
    Li,
    Main,
    Nav,
    P,
    Span,
    Strong,
    Ul,
)

logger = logging.getLogger(__name__)


def nav() -> Nav:
    """Top navigation bar with approved-jobs count badge on the Jobs link."""
    approved_count = 0
    try:
        from applybot.models.job import Job

        approved_count = Job.count_by_status().get("approved", 0)
    except Exception:
        logger.warning(
            "Failed to fetch approved job count for nav badge", exc_info=True
        )

    jobs_link = (
        A(
            "Jobs",
            Span(str(approved_count), cls="nav-badge"),
            href="/jobs",
        )
        if approved_count > 0
        else A("Jobs", href="/jobs")
    )

    return Nav(
        Ul(Li(Strong(A("ApplyBot", href="/")))),
        Ul(
            Li(A("Overview", href="/")),
            Li(jobs_link),
            Li(A("Applications", href="/apps")),
            Li(A("Profile", href="/profile")),
            Li(
                Form(
                    Button("Logout", type="submit", cls="secondary outline"),
                    method="post",
                    action="/logout",
                    style="margin:0",
                )
            ),
        ),
    )


def page(*content: object, title: str = "ApplyBot") -> tuple[object, ...]:
    """Wrap content in the standard page layout with nav."""
    return (
        nav(),
        Main(Container(*content), cls="container"),
    )


def alert(msg: str, kind: str = "info") -> Article:
    """Render a themed alert. kind: info, success, error."""
    role = {"info": "note", "success": "status", "error": "alert"}.get(kind, "note")
    return Article(P(msg), role=role)
