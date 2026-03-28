"""Overview page — dashboard stats and pipeline view."""

from __future__ import annotations

import logging
from typing import Any

from fasthtml.common import H1, H2, Article, Button, Div, Grid, Span

from applybot.dashboard.components import alert, page, progress_table, stat_card
from applybot.discovery.orchestrator import run_discovery
from applybot.models.application import count_applications_by_status
from applybot.models.job import count_jobs_by_status

logger = logging.getLogger(__name__)

PIPELINE_STAGES = ["new", "reviewing", "approved", "applied"]


def register(rt: Any) -> None:
    @rt("/", methods=["get"])
    def get() -> tuple[object, ...]:
        job_counts = count_jobs_by_status()
        total_jobs = job_counts.get("total", 0)

        app_counts = count_applications_by_status()
        total_apps = app_counts.get("total", 0)

        stats = Grid(
            stat_card(str(total_jobs), "Total Jobs"),
            stat_card(str(job_counts.get("new", 0)), "New Jobs"),
            stat_card(str(total_apps), "Applications"),
            stat_card(str(app_counts.get("interview", 0)), "Interviews"),
        )

        pipeline = progress_table(
            "Pipeline",
            [(s.capitalize(), job_counts.get(s, 0)) for s in PIPELINE_STAGES],
        )

        app_section = ""
        if total_apps > 0:
            app_section = progress_table(
                "Application Statuses",
                [
                    (s.replace("_", " ").capitalize(), c)
                    for s, c in app_counts.items()
                    if s != "total"
                ],
            )

        actions_section = Article(
            H2("Actions", cls="section-eyebrow"),
            Div(
                Span(cls="htmx-indicator staging-spinner", id="discover-spinner"),
                Button(
                    "Run Discovery Now",
                    hx_post="/discover",
                    hx_target="#discover-result",
                    hx_swap="innerHTML",
                    hx_indicator="#discover-spinner",
                    cls="build-btn",
                ),
                cls="staging-header-right",
            ),
            Div(id="discover-result", cls="staging-result"),
        )

        return page(
            H1("Dashboard Overview"),
            stats,
            pipeline,
            app_section,
            actions_section,
            title="Overview",
        )

    @rt("/discover", methods=["post"])
    async def post_discover() -> object:
        try:
            result = await run_discovery()
            msg = f"Found {result.total_scraped} jobs · {result.new_jobs_saved} new after deduplication"
            return alert(msg, "success")
        except Exception as e:
            logger.exception("Discovery failed")
            return alert(f"Discovery failed: {str(e)[:150]}", "error")
