"""Overview page — dashboard stats and pipeline view."""

from __future__ import annotations

from typing import Any

from fasthtml.common import H1, Grid

from applybot.dashboard.components import page, progress_table, stat_card
from applybot.models.application import Application, ApplicationStatus
from applybot.models.base import get_session
from applybot.models.job import Job, JobStatus

PIPELINE_STAGES = ["new", "reviewing", "approved", "applied"]


def register(rt: Any) -> None:
    @rt("/")
    def get() -> tuple[object, ...]:
        with get_session() as session:
            job_counts: dict[str, int] = {}
            for status in JobStatus:
                count = session.query(Job).filter(Job.status == status).count()
                if count > 0:
                    job_counts[status.value] = count
            total_jobs = session.query(Job).count()

            app_counts: dict[str, int] = {}
            for app_status in ApplicationStatus:
                count = (
                    session.query(Application)
                    .filter(Application.status == app_status)
                    .count()
                )
                if count > 0:
                    app_counts[app_status.value] = count
            total_apps = session.query(Application).count()

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
                [(s.replace("_", " ").capitalize(), c) for s, c in app_counts.items()],
            )

        return page(
            H1("Dashboard Overview"), stats, pipeline, app_section, title="Overview"
        )
