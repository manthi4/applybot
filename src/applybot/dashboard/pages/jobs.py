"""Job queue page — list, filter, approve, skip, build applications."""

from __future__ import annotations

import logging
from typing import Any

from fasthtml.common import H1, H4, A, Article, Button, Div, NotStr, P, Small, Span

from applybot.application.preparer import prepare_all_approved
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

logger = logging.getLogger(__name__)


def _job_status_options(current: str) -> list[tuple[str, str]]:
    return [("", "All")] + [(s.value, s.value.capitalize()) for s in JobStatus]


def _score_chip(score_val: float | None) -> Span:
    score_text = f"Score {score_val:.0f}" if score_val is not None else "Score N/A"
    if score_val is None:
        cls = "score-chip"
    elif score_val >= 70:
        cls = "score-chip score-high"
    elif score_val >= 40:
        cls = "score-chip score-mid"
    else:
        cls = "score-chip score-low"
    return Span(score_text, cls=cls)


def _build_staging_card(job: Job) -> Div:
    """Compact tile for an approved job in the staging area."""
    return Div(
        Div(
            Div(job.title, cls="staging-card-title"),
            Div(job.company, cls="staging-card-company"),
            cls="staging-card-text",
        ),
        Div(
            _score_chip(job.relevance_score),
            Button(
                "✕",
                hx_post=f"/jobs/{job.id}/unapprove",
                hx_target="#staging-area",
                hx_swap="outerHTML",
                hx_confirm=f"Remove '{job.title}' from staging? It will return to New.",
                cls="staging-remove-btn",
                title="Remove from staging",
            ),
            cls="staging-card-actions",
        ),
        cls="staging-card",
        id=f"staging-{job.id}",
    )


def _build_staging_area(approved_jobs: list[Job], *, oob: bool = False) -> Div:
    """Staging area showing approved jobs queued for LLM application generation."""
    count = len(approved_jobs)
    count_badge_cls = (
        "staging-count staging-count-active" if count > 0 else "staging-count"
    )

    if count == 0:
        body = Div(
            Span(
                "No approved jobs waiting. Use Approve on jobs below to queue them here.",
                cls="staging-empty-msg",
            ),
            cls="staging-body",
        )
    else:
        body = Div(
            *[_build_staging_card(j) for j in approved_jobs],
            cls="staging-body staging-grid",
        )

    est_mins = max(1, count * 2)
    confirm_msg = (
        f"Build applications for {count} job{'s' if count != 1 else ''}? "
        f"~{est_mins} min estimated (3 LLM calls per job)."
        if count > 0
        else None
    )

    extra_kwargs: dict[str, Any] = {}
    if oob:
        extra_kwargs["hx_swap_oob"] = "outerHTML"

    return Div(
        Div(
            Div(
                Span("Staging Area", cls="section-eyebrow"),
                Span(
                    f"{count} job{'s' if count != 1 else ''} queued",
                    cls=count_badge_cls,
                ),
                cls="staging-header-left",
            ),
            Div(
                Span(cls="htmx-indicator staging-spinner", id="build-spinner"),
                Button(
                    "Unstage All",
                    hx_post="/jobs/unstage-all",
                    hx_target="#staging-area",
                    hx_swap="outerHTML",
                    hx_confirm=(
                        f"Remove all {count} approved job{'s' if count != 1 else ''}"
                        " from staging? They will return to New."
                        if count > 0
                        else None
                    ),
                    disabled=True if count == 0 else None,
                    cls="unstage-all-btn",
                ),
                Button(
                    "Build Approved Applications",
                    hx_post="/jobs/build-approved",
                    hx_target="#build-result",
                    hx_swap="innerHTML",
                    hx_indicator="#build-spinner",
                    hx_confirm=confirm_msg,
                    disabled=True if count == 0 else None,
                    cls="build-btn",
                ),
                cls="staging-header-right",
            ),
            cls="staging-header",
        ),
        body,
        Div(id="build-result", cls="staging-result"),
        cls="staging-area",
        id="staging-area",
        **extra_kwargs,
    )


def _build_job_card(job: Job) -> Article:
    status_str = job.status.value if hasattr(job.status, "value") else str(job.status)
    source_str = job.source.value if hasattr(job.source, "value") else str(job.source)

    header = Div(
        Div(
            H4(job.title, style="margin:0 0 0.2rem 0;color:var(--text)"),
            Small(
                f"{job.company}"
                + (f" · {job.location}" if job.location else "")
                + f" · {source_str}"
            ),
            style="flex:1;min-width:0",
        ),
        Div(
            _score_chip(job.relevance_score),
            status_badge(status_str),
            style="display:flex;align-items:center;gap:0.5rem;flex-shrink:0;margin-top:0.15rem",
        ),
        style="display:flex;align-items:flex-start;gap:1rem",
    )

    meta_parts: list[object] = []
    if job.relevance_reasoning:
        meta_parts.append(
            Div(
                Span("Match", cls="meta-label"),
                Span(job.relevance_reasoning, cls="meta-value"),
                cls="job-meta-row",
            )
        )
    if job.url:
        meta_parts.append(
            P(
                A("View Job Posting", href=job.url, target="_blank"),
                style="margin:0.4rem 0 0;font-size:0.88rem",
            )
        )

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
    @rt("/jobs", methods=["get"])
    def get(status: str = "new", min_score: int = 0) -> tuple[object, ...]:
        # Always load approved jobs for the staging area (independent of browse filter)
        approved_jobs = query_jobs(status=JobStatus.APPROVED, limit=100)

        # Browse section: defaults to showing NEW jobs
        job_status: JobStatus | None = None
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

        staging = _build_staging_area(approved_jobs)

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

        status_label = job_status.value.capitalize() if job_status else "All"
        count_text = P(
            f"{len(jobs)} {status_label.lower()} job{'s' if len(jobs) != 1 else ''} found",
            style="color:var(--text-2);font-size:0.85rem;margin:0.5rem 0 0.75rem",
        )
        cards = [_build_job_card(j) for j in jobs] or [
            alert("No jobs found matching your filters.")
        ]

        return page(
            H1("Job Queue"),
            staging,
            Div(
                Span("Browse Jobs", cls="section-eyebrow"),
                form,
                count_text,
                *cards,
                cls="jobs-browse-section",
            ),
            title="Job Queue",
        )

    @rt("/jobs/build-approved", methods=["post"])
    def post_build() -> object:
        """Trigger LLM application preparation for all approved jobs."""
        try:
            results = prepare_all_approved()
            n = len(results)
            if n == 0:
                result_alert = alert("No approved jobs found to build.", "info")
            else:
                total_gaps = sum(len(gaps) for _, gaps in results)
                msg = f"Built {n} application{'s' if n != 1 else ''} — now in the review queue."
                if total_gaps:
                    msg += f" {total_gaps} profile gap{'s' if total_gaps != 1 else ''} flagged."
                result_alert = alert(msg, "success")
        except ValueError as e:
            logger.exception("Build approved: profile error")
            result_alert = alert(f"Profile error: {e}", "error")
        except Exception as e:
            logger.exception("Build approved: unexpected error")
            result_alert = alert(f"Unexpected error: {str(e)[:150]}", "error")

        # OOB-refresh staging area (approved jobs are now in REVIEWING)
        new_approved = query_jobs(status=JobStatus.APPROVED, limit=100)
        oob = _build_staging_area(new_approved, oob=True)
        return NotStr(str(result_alert) + str(oob))

    @rt("/jobs/unstage-all", methods=["post"])
    def post_unstage_all() -> object:
        """Return all approved jobs back to NEW, clearing the staging area."""
        approved = query_jobs(status=JobStatus.APPROVED, limit=100)
        for job in approved:
            update_job(job.id, status=JobStatus.NEW)
        return _build_staging_area([])

    @rt("/jobs/{job_id}/unapprove", methods=["post"])
    def post_unapprove(job_id: str) -> object:
        """Return an approved job back to NEW, removing it from the staging area."""
        job = get_job(job_id)
        if job is None:
            return alert("Job not found.", "error")
        update_job(job_id, status=JobStatus.NEW)
        new_approved = query_jobs(status=JobStatus.APPROVED, limit=100)
        return _build_staging_area(new_approved)

    @rt("/jobs/{job_id}/approve", methods=["post"])
    def post(job_id: str) -> object:
        job = get_job(job_id)
        if job is None:
            return alert("Job not found.", "error")
        if job.status != JobStatus.NEW:
            return alert(f"Job is {job.status.value}, not new.", "error")
        update_job(job_id, status=JobStatus.APPROVED)
        card = confirmed_card(
            "job",
            job.id,
            f"{job.title} at {job.company}",
            "Approved — added to staging",
        )
        # OOB-refresh staging area so the new tile appears immediately
        new_approved = query_jobs(status=JobStatus.APPROVED, limit=100)
        oob = _build_staging_area(new_approved, oob=True)
        return NotStr(str(card) + str(oob))

    @rt("/jobs/{job_id}/skip", methods=["post"])
    def post_skip(job_id: str) -> object:
        job = get_job(job_id)
        if job is None:
            return alert("Job not found.", "error")
        update_job(job_id, status=JobStatus.SKIPPED)
        return confirmed_card("job", job.id, f"{job.title} at {job.company}", "Skipped")
