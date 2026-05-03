"""Applications page — list, filter, approve, and rich inline editing."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fasthtml.common import (
    H1,
    H4,
    A,
    Button,
    Div,
    Form,
    Input,
    Label,
    P,
    Pre,
    Small,
    Span,
    Strong,
    Textarea,
)
from starlette.requests import Request
from starlette.responses import Response

from applybot.dashboard.components import (
    alert,
    confirmed_card,
    detail_card,
    filter_form,
    page,
    status_badge,
)
from applybot.models.application import (
    Application,
    ApplicationStatus,
    UpdateSource,
    get_application,
    query_applications,
    update_application,
)
from applybot.models.job import Job, get_job
from applybot.tracking.tracker import InvalidTransitionError, update_status

_TERMINAL = {ApplicationStatus.REJECTED, ApplicationStatus.WITHDRAWN}


def _app_status_options(current: str) -> list[tuple[str, str]]:
    return [("", "All")] + [
        (s.value, s.value.replace("_", " ").capitalize()) for s in ApplicationStatus
    ]


def _build_gap_section(gaps: list[dict[str, str]]) -> Div:
    """Render a warning section for profile gaps."""
    items = [
        Div(
            Span("⚠", cls="gap-icon"),
            Div(
                Div(g.get("question", ""), cls="gap-question"),
                Div(g.get("context", ""), cls="gap-context"),
            ),
            cls="gap-item",
        )
        for g in gaps
    ]
    n = len(gaps)
    return Div(
        Div(
            Span(f"⚠ {n} Profile Gap{'s' if n != 1 else ''}", cls="gap-header-label"),
            Span(
                "These questions couldn't be answered from your profile.",
                cls="gap-header-sub",
            ),
            cls="gap-header",
        ),
        *items,
        cls="gap-section",
    )


# -- Cover-letter fragment ---------------------------------------------------


def _cover_letter_section(
    app_id: str, cover_letter: str, *, terminal: bool = False, saved: bool = False
) -> Div:
    """Cover-letter section — editable normally, read-only for terminal statuses."""
    if terminal:
        body: object = (
            Pre(cover_letter, cls="cover-letter-pre")
            if cover_letter
            else P(Small("No cover letter."), style="margin:0")
        )
    else:
        body = Form(
            Textarea(
                cover_letter or "",
                name="cover_letter",
                rows="14",
                style="width:100%;font-family:'JetBrains Mono',monospace;font-size:0.85em;",
            ),
            Div(
                Button(
                    "Save Cover Letter",
                    type="submit",
                    hx_post=f"/apps/{app_id}/cover-letter",
                    hx_target=f"#cover-letter-section-{app_id}",
                    hx_swap="outerHTML",
                    hx_include="closest form",
                    cls="qa-save-btn secondary",
                ),
            ),
        )
    children: list[object] = [H4("Cover Letter"), body]
    if saved:
        children.append(
            P(
                "Cover letter saved.",
                style="font-size:0.8em;color:#4ade80;margin:0.25rem 0 0",
            )
        )
    return Div(*children, id=f"cover-letter-section-{app_id}", cls="app-section")


# -- Resume fragment ----------------------------------------------------------


def _resume_section(app: Application, *, terminal: bool = False) -> Div:
    """Tailored-resume section fragment."""
    app_id = app.id
    if not terminal:
        extra: list[object] = [
            Button(
                "Re-tailor Resume",
                hx_post=f"/apps/{app_id}/retailor",
                hx_target=f"#resume-section-{app_id}",
                hx_swap="outerHTML",
                hx_indicator=f"#retailor-ind-{app_id}",
                cls="retailor-btn secondary",
            ),
            Span(
                "Working...",
                id=f"retailor-ind-{app_id}",
                cls="htmx-indicator",
                style="font-size:0.8em;color:var(--text-2)",
            ),
        ]
    else:
        extra = []
    if app.tailored_resume_path:
        filename = Path(app.tailored_resume_path).name
        body = Div(
            A(filename, href=f"/apps/{app_id}/resume/download", cls="resume-download"),
            *extra,
            cls="resume-section",
        )
    else:
        body = Div(
            P(Small("No tailored resume generated."), style="margin:0"),
            *extra,
            cls="resume-section",
        )
    return Div(
        H4("Tailored Resume"),
        body,
        id=f"resume-section-{app_id}",
        cls="app-section",
    )


# -- Q&A fragment -------------------------------------------------------------


def _qa_section(
    app: Application, *, terminal: bool = False, saved: bool = False
) -> Div:
    """Q&A answers section fragment — editable normally, read-only for terminal statuses."""
    app_id = app.id
    if not app.answers:
        return Div(
            H4("Q&A Answers"),
            P(Small("No questions for this application."), style="margin:0"),
            id=f"qa-section-{app_id}",
            cls="app-section",
        )
    if terminal:
        body: object = Div(
            *[
                Div(
                    Label(question),
                    P(answer or "(no answer)", style="margin:0;font-size:0.9em;"),
                    cls="qa-item",
                )
                for question, answer in app.answers.items()
            ]
        )
    else:
        form_items = []
        for i, (question, answer) in enumerate(app.answers.items()):
            form_items.append(
                Div(
                    Input(type="hidden", name=f"q_{i}", value=question),
                    Label(question, _for=f"a_{i}"),
                    Textarea(answer or "", name=f"a_{i}", id=f"a_{i}", rows="3"),
                    cls="qa-item",
                )
            )
        body = Form(
            *form_items,
            Div(
                Button(
                    "Save Answers",
                    type="submit",
                    hx_post=f"/apps/{app_id}/answers",
                    hx_target=f"#qa-section-{app_id}",
                    hx_swap="outerHTML",
                    hx_include="closest form",
                    cls="qa-save-btn secondary",
                ),
            ),
        )
    children: list[object] = [H4("Q&A Answers"), body]
    if saved:
        children.append(
            P(
                "Answers saved.",
                style="font-size:0.8em;color:#4ade80;margin:0.25rem 0 0",
            )
        )
    return Div(*children, id=f"qa-section-{app_id}", cls="app-section")


# -- Main card builder --------------------------------------------------------


def _build_app_card(application: Application, job: Job | None) -> object:
    app_id = application.id
    job_title = job.title if job else "Unknown Job"
    job_company = job.company if job else f"Job #{application.job_id}"
    score = getattr(job, "relevance_score", None) if job else None

    status_str = application.status.value.replace("_", " ").capitalize()
    summary_text = f"{job_title} @ {job_company} -- {status_str}"
    if score is not None:
        summary_text += f"  |  Score {score:.0f}"

    # Section: Details
    details_items: list[object] = [
        P(
            Strong("Status: "),
            status_badge(application.status.value),
            "  ",
            Strong("Created: "),
            str(application.created_at)[:19] if application.created_at else "---",
        )
    ]
    if application.submitted_at:
        details_items.append(
            P(Strong("Submitted: "), str(application.submitted_at)[:19])
        )
    if (
        application.profile_gaps
        and application.status == ApplicationStatus.READY_FOR_REVIEW
    ):
        details_items.append(_build_gap_section(application.profile_gaps))
    details_section = Div(H4("Details"), *details_items, cls="app-section")

    # Section: Actions
    action_items: list[object] = []
    if application.status == ApplicationStatus.READY_FOR_REVIEW:
        action_items.append(
            Button(
                "Approve",
                hx_post=f"/apps/{app_id}/approve",
                hx_target=f"#app-{app_id}",
                hx_swap="outerHTML",
            )
        )
    if application.status not in _TERMINAL:
        action_items.append(
            Button(
                "Withdraw",
                hx_post=f"/apps/{app_id}/withdraw",
                hx_target=f"#app-{app_id}",
                hx_swap="outerHTML",
                cls="secondary outline",
            )
        )
    actions_sec: object = (
        Div(
            H4("Actions"),
            Div(*action_items, style="display:flex;gap:0.5rem;flex-wrap:wrap"),
            cls="app-section",
        )
        if action_items
        else None
    )

    is_terminal = application.status in _TERMINAL
    sections: list[object] = [
        details_section,
        _resume_section(application, terminal=is_terminal),
        _cover_letter_section(app_id, application.cover_letter, terminal=is_terminal),
        _qa_section(application, terminal=is_terminal),
    ]
    if actions_sec is not None:
        sections.append(actions_sec)

    return detail_card("app", app_id, summary_text, *sections)


# -- Route registration -------------------------------------------------------


def register(rt: Any) -> None:
    @rt("/apps", methods=["get"])
    def get(status: str = "") -> tuple[object, ...]:
        app_status = None
        if status:
            try:
                app_status = ApplicationStatus(status)
            except ValueError:
                pass
        apps = query_applications(status=app_status, limit=200)

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
        cards = [_build_app_card(app, get_job(app.job_id)) for app in apps] or [
            alert("No applications found.")
        ]
        return page(H1("Applications"), form, count_text, *cards, title="Applications")

    # -- Status transitions ---------------------------------------------------

    @rt("/apps/{app_id}/approve", methods=["post"])
    def post_approve(app_id: str) -> object:
        try:
            update_status(app_id, ApplicationStatus.APPROVED, UpdateSource.MANUAL)
            return confirmed_card("app", app_id, f"Application #{app_id}", "Approved")
        except (ValueError, InvalidTransitionError) as e:
            return alert(str(e), "error")

    @rt("/apps/{app_id}/withdraw", methods=["post"])
    def post_withdraw(app_id: str) -> object:
        try:
            update_status(app_id, ApplicationStatus.WITHDRAWN, UpdateSource.MANUAL)
            return confirmed_card("app", app_id, f"Application #{app_id}", "Withdrawn")
        except (ValueError, InvalidTransitionError) as e:
            return alert(str(e), "error")

    # -- Cover-letter save ----------------------------------------------------

    @rt("/apps/{app_id}/cover-letter", methods=["post"])
    def post_cover_letter(app_id: str, cover_letter: str = "") -> object:
        app = get_application(app_id)
        if app is None:
            return alert(f"Application {app_id} not found.", "error")
        update_application(app_id, cover_letter=cover_letter)
        return _cover_letter_section(app_id, cover_letter, saved=True)

    # -- Q&A answers save -----------------------------------------------------

    @rt("/apps/{app_id}/answers", methods=["post"])
    async def post_answers(app_id: str, request: Request) -> object:
        app = get_application(app_id)
        if app is None:
            return alert(f"Application {app_id} not found.", "error")
        form = await request.form()
        answers: dict[str, str] = {}
        i = 0
        while f"q_{i}" in form:
            question = str(form[f"q_{i}"])
            answer = str(form.get(f"a_{i}", ""))
            if question:
                answers[question] = answer
            i += 1
        update_application(app_id, answers=answers)
        app.answers = answers
        return _qa_section(app, saved=True)

    # -- Resume re-tailor -----------------------------------------------------

    @rt("/apps/{app_id}/retailor", methods=["post"])
    def post_retailor(app_id: str) -> object:
        app = get_application(app_id)
        if app is None:
            return alert(f"Application {app_id} not found.", "error")
        job = get_job(app.job_id)
        if job is None:
            return alert(f"Job {app.job_id} not found for this application.", "error")
        try:
            from applybot.application.resume_tailor import tailor_resume
            from applybot.profile.manager import ProfileManager

            profile = ProfileManager().get_profile()
            if profile is None:
                return alert("No profile found -- cannot re-tailor resume.", "error")
            new_path = tailor_resume(job, profile)
            update_application(app_id, tailored_resume_path=str(new_path))
            app.tailored_resume_path = str(new_path)
            return _resume_section(app)
        except Exception as exc:
            return alert(f"Re-tailor failed: {exc}", "error")

    # -- Resume download ------------------------------------------------------

    @rt("/apps/{app_id}/resume/download", methods=["get"])
    def get_resume_download(app_id: str) -> object:
        app = get_application(app_id)
        if app is None or not app.tailored_resume_path:
            return alert("Resume not found.", "error")
        try:
            from applybot.storage import download_file

            content = download_file(app.tailored_resume_path)
            filename = Path(app.tailored_resume_path).name
            return Response(
                content=content,
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
        except Exception as exc:
            return alert(f"Download failed: {exc}", "error")
