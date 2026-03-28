"""Job queue page — list, filter, approve, skip."""

from __future__ import annotations

from typing import Any

from fasthtml.common import H1, H4, A, Article, Div, P, Small, Strong

from applybot.dashboard.components import (
    action_buttons,
    alert,
    collapsible_text,
    confirmed_card,
    filter_form,
    page,
    status_badge,
)
from applybot.models.job import Job, JobStatus, get_job, query_jobs, update_job


def _job_status_options(current: str) -> list[tuple[str, str]]:
    return [("", "All")] + [(s.value, s.value.capitalize()) for s in JobStatus]


def _build_job_card(job: Job) -> object:
    score = f"{job.relevance_score:.0f}" if job.relevance_score is not None else "N/A"
    source_str = job.source.value if hasattr(job.source, "value") else str(job.source)
    status_str = job.status.value if hasattr(job.status, "value") else str(job.status)

    header = Div(
        Div(
            H4(f"{job.title} at {job.company}", style="margin:0"),
            Small(f"Score: {score} · {job.location} · {source_str}"),
            style="flex:1",
        ),
        Div(status_badge(status_str), style="align-self:center;margin-left:1rem"),
        style="display:flex;align-items:flex-start;gap:0.5rem",
    )

    meta_parts: list[object] = []
    if job.relevance_reasoning:
        meta_parts.append(P(Strong("Match: "), job.relevance_reasoning))
    if job.url:
        meta_parts.append(P(A("View Job Posting ↗", href=job.url, target="_blank")))

    actions: list[object] = []
    if job.status == JobStatus.NEW:
        actions.append(
            action_buttons(
                ("Approve", f"/jobs/{job.id}/approve", f"#job-{job.id}", ""),
                ("Skip", f"/jobs/{job.id}/skip", f"#job-{job.id}", "secondary"),
            )
        )

    desc_section: list[object] = []
    if job.description:
        desc_section.append(collapsible_text("Description", job.description[:2000]))

    return Article(
        header,
        *meta_parts,
        *actions,
        *desc_section,
        id=f"job-{job.id}",
    )


def register(rt: Any) -> None:
    @rt("/jobs")
    def get(status: str = "", min_score: int = 0) -> tuple[object, ...]:
        job_status = None
        if status:
            try:
                job_status = JobStatus(status)
            except ValueError:
                pass
        jobs = query_jobs(
            status=job_status,
            min_score=min_score if min_score > 0 else None,
            limit=200,
        )

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
    def post(job_id: str) -> object:
        job = get_job(job_id)
        if job is None:
            return alert("Job not found.", "error")
        if job.status != JobStatus.NEW:
            return alert(f"Job is {job.status.value}, not new.", "error")
        update_job(job_id, status=JobStatus.APPROVED)
        return confirmed_card(
            "job", job.id, f"{job.title} at {job.company}", "Approved"
        )

    @rt("/jobs/{job_id}/skip")
    def post_skip(job_id: str) -> object:
        job = get_job(job_id)
        if job is None:
            return alert("Job not found.", "error")
        update_job(job_id, status=JobStatus.SKIPPED)
        return confirmed_card("job", job.id, f"{job.title} at {job.company}", "Skipped")
