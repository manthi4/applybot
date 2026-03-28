"""Overview page — dashboard stats and pipeline view."""

from __future__ import annotations

from typing import Any

from fasthtml.common import H1, Grid

from applybot.dashboard.components import page, progress_table, stat_card
from applybot.models.application import count_applications_by_status
from applybot.models.job import count_jobs_by_status

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

        return page(
            H1("Dashboard Overview"), stats, pipeline, app_section, title="Overview"
        )
