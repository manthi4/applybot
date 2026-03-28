"""Overview page — dashboard stats and pipeline view."""

from __future__ import annotations

import logging
from typing import Any

from fasthtml.common import H1, Article, Button, Div, Grid, NotStr, Span, to_xml

from applybot.dashboard.components import alert, page, progress_table, stat_card
from applybot.discovery.orchestrator import run_discovery
from applybot.models.application import count_applications_by_status
from applybot.models.job import count_jobs_by_status

logger = logging.getLogger(__name__)

PIPELINE_STAGES = ["new", "reviewing", "approved", "applied"]


def _build_stats_grid(
    *,
    oob: bool = False,
    job_counts: dict[str, int] | None = None,
    app_counts: dict[str, int] | None = None,
) -> Grid:
    if job_counts is None:
        job_counts = count_jobs_by_status()
    if app_counts is None:
        app_counts = count_applications_by_status()
    extra: dict[str, Any] = {"id": "overview-stats"}
    if oob:
        extra["hx_swap_oob"] = "outerHTML"
    return Grid(
        stat_card(str(job_counts.get("total", 0)), "Total Jobs"),
        stat_card(str(job_counts.get("new", 0)), "New Jobs"),
        stat_card(str(app_counts.get("total", 0)), "Applications"),
        stat_card(str(app_counts.get("interview", 0)), "Interviews"),
        **extra,
    )


def register(rt: Any) -> None:
    @rt("/", methods=["get"])
    def get() -> tuple[object, ...]:
        job_counts = count_jobs_by_status()
        app_counts = count_applications_by_status()
        total_apps = app_counts.get("total", 0)

        stats = _build_stats_grid(job_counts=job_counts, app_counts=app_counts)

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
            Span("Actions", cls="section-eyebrow"),
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
            msg = (
                f"Scraped {result.total_scraped}"
                f" · {result.after_dedup} unique"
                f" · {result.above_threshold} above threshold"
                f" · {result.new_jobs_saved} new saved"
            )
            result_alert = alert(msg, "success")
            stats_oob = _build_stats_grid(oob=True)
            return NotStr(to_xml(result_alert) + to_xml(stats_oob))
        except Exception as e:
            logger.exception("Discovery failed")
            return alert(f"Discovery failed: {str(e)[:150]}", "error")
