"""Applications page — list, filter, approve, return to draft."""

from __future__ import annotations

from typing import Any

from fasthtml.common import H1, Hr, P, Strong

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
from applybot.models.application import Application, ApplicationStatus, UpdateSource
from applybot.models.base import get_session
from applybot.models.job import Job
from applybot.tracking.tracker import InvalidTransitionError, update_status


def _app_status_options(current: str) -> list[tuple[str, str]]:
    return [("", "All")] + [
        (s.value, s.value.replace("_", " ").capitalize()) for s in ApplicationStatus
    ]


def _build_app_card(application: Application, job: Job | None) -> object:
    job_label = f"{job.title} at {job.company}" if job else f"Job #{application.job_id}"
    summary_text = (
        f"{job_label} -- {application.status.value.replace('_', ' ').capitalize()}"
    )

    content = [
        P(
            Strong("Status: "),
            status_badge(application.status.value),
            " | ",
            Strong("Created: "),
            str(application.created_at)[:19] if application.created_at else "---",
        ),
    ]
    if application.submitted_at:
        content.append(P(Strong("Submitted: "), str(application.submitted_at)[:19]))
    if application.cover_letter:
        content.append(collapsible_text("Cover Letter", application.cover_letter))
    if application.answers:
        qa_items = []
        for q, a in application.answers.items():
            qa_items.extend([P(Strong("Q: "), q), P("A: ", a), Hr()])
        from fasthtml.common import Details, Summary

        content.append(Details(Summary("Application Answers"), *qa_items))
    if application.tailored_resume_path:
        content.append(P(Strong("Tailored resume: "), application.tailored_resume_path))
    if application.status == ApplicationStatus.READY_FOR_REVIEW:
        content.append(
            action_buttons(
                (
                    "Approve",
                    f"/apps/{application.id}/approve",
                    f"#app-{application.id}",
                    "",
                ),
                (
                    "Back to Draft",
                    f"/apps/{application.id}/draft",
                    f"#app-{application.id}",
                    "secondary",
                ),
            )
        )
    return detail_card("app", application.id, summary_text, *content)


def register(rt: Any) -> None:
    @rt("/apps")
    def get(status: str = "") -> tuple[object, ...]:
        with get_session() as session:
            query = session.query(Application)
            if status:
                try:
                    query = query.filter(
                        Application.status == ApplicationStatus(status)
                    )
                except ValueError:
                    pass
            query = query.order_by(Application.created_at.desc())
            apps = query.limit(200).all()

            form = filter_form(
                "/apps",
                [
                    {
                        "name": "status",
                        "label": "Status",
                        "type": "select",
                        "options": _app_status_options(status),
                        "selected": status,
                    },
                ],
            )
            count_text = P(Strong(f"{len(apps)} applications"))
            cards = [
                _build_app_card(app, session.get(Job, app.job_id)) for app in apps
            ] or [alert("No applications found.")]

        return page(H1("Applications"), form, count_text, *cards, title="Applications")

    @rt("/apps/{app_id}/approve")
    def post(app_id: int) -> object:
        try:
            update_status(app_id, ApplicationStatus.APPROVED, UpdateSource.MANUAL)
            return confirmed_card("app", app_id, f"Application #{app_id}", "Approved")
        except (ValueError, InvalidTransitionError) as e:
            return alert(str(e), "error")

    @rt("/apps/{app_id}/draft")
    def post_draft(app_id: int) -> object:
        try:
            update_status(app_id, ApplicationStatus.DRAFT, UpdateSource.MANUAL)
            return confirmed_card(
                "app", app_id, f"Application #{app_id}", "Back to Draft"
            )
        except (ValueError, InvalidTransitionError) as e:
            return alert(str(e), "error")
