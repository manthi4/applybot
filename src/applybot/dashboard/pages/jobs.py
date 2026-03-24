"""Job queue page — list, filter, approve, skip."""

from __future__ import annotations

from typing import Any

from fasthtml.common import H1, A, P, Strong

from applybot.dashboard.components import (
    action_buttons,
    alert,
    collapsible_text,
    confirmed_card,
    detail_card,
    filter_form,
    page,
    status_badge,
)
from applybot.models.base import get_session
from applybot.models.job import Job, JobStatus


def _job_status_options(current: str) -> list[tuple[str, str]]:
    return [("", "All")] + [(s.value, s.value.capitalize()) for s in JobStatus]


def _build_job_card(job: Job) -> object:
    score = (
        f"Score: {job.relevance_score:.0f}"
        if job.relevance_score is not None
        else "Score: N/A"
    )
    header = f"{job.title} at {job.company} -- {score}"

    content = [
        P(
            Strong("Location: "),
            job.location,
            " | ",
            Strong("Source: "),
            job.source.value,
            " | ",
            Strong("Status: "),
            status_badge(job.status.value),
        ),
    ]
    if job.relevance_reasoning:
        content.append(P(Strong("Match reasoning: "), job.relevance_reasoning))
    if job.url:
        content.append(P(A("View Job Posting", href=job.url, target="_blank")))
    if job.description:
        content.append(collapsible_text("Description", job.description[:2000]))
    if job.status == JobStatus.NEW:
        content.append(
            action_buttons(
                ("Approve", f"/jobs/{job.id}/approve", f"#job-{job.id}", ""),
                ("Skip", f"/jobs/{job.id}/skip", f"#job-{job.id}", "secondary"),
            )
        )
    return detail_card("job", job.id, header, *content)


def register(rt: Any) -> None:
    @rt("/jobs")
    def get(status: str = "", min_score: int = 0) -> tuple[object, ...]:
        with get_session() as session:
            query = session.query(Job)
            if status:
                try:
                    query = query.filter(Job.status == JobStatus(status))
                except ValueError:
                    pass
            if min_score > 0:
                query = query.filter(Job.relevance_score >= min_score)
            query = query.order_by(Job.relevance_score.desc().nullslast())
            jobs = query.limit(200).all()

            form = filter_form(
                "/jobs",
                [
                    {
                        "name": "status",
                        "label": "Status",
                        "type": "select",
                        "options": _job_status_options(status),
                        "selected": status,
                    },
                    {
                        "name": "min_score",
                        "label": "Min Score",
                        "type": "number",
                        "value": min_score,
                        "min": 0,
                        "max": 100,
                    },
                ],
            )
            count_text = P(Strong(f"{len(jobs)} jobs found"))
            cards = [_build_job_card(j) for j in jobs] or [
                alert("No jobs found matching your filters.")
            ]

        return page(H1("Job Queue"), form, count_text, *cards, title="Job Queue")

    @rt("/jobs/{job_id}/approve")
    def post(job_id: int) -> object:
        with get_session() as session:
            job = session.get(Job, job_id)
            if job is None:
                return alert("Job not found.", "error")
            if job.status != JobStatus.NEW:
                return alert(f"Job is {job.status.value}, not new.", "error")
            job.status = JobStatus.APPROVED
            session.commit()
            return confirmed_card(
                "job", job.id, f"{job.title} at {job.company}", "Approved"
            )

    @rt("/jobs/{job_id}/skip")
    def post_skip(job_id: int) -> object:
        with get_session() as session:
            job = session.get(Job, job_id)
            if job is None:
                return alert("Job not found.", "error")
            job.status = JobStatus.SKIPPED
            session.commit()
            return confirmed_card(
                "job", job.id, f"{job.title} at {job.company}", "Skipped"
            )
