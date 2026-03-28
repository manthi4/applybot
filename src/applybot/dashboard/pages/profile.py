"""Profile page — view and edit user profile."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fasthtml.common import (
    H1,
    H3,
    Button,
    Details,
    Div,
    Form,
    Input,
    Label,
    P,
    Pre,
    RedirectResponse,
    Span,
    Summary,
    Textarea,
)
from starlette.requests import Request

from applybot.dashboard.components import alert, page
from applybot.models.profile import UserProfile, get_profile, save_profile
from applybot.profile.resume import parse_resume

logger = logging.getLogger(__name__)

_FLASH_MESSAGES: dict[str, tuple[str, str]] = {
    "basic_saved": ("Basic profile info saved.", "success"),
    "resume_uploaded": ("Resume uploaded and parsed successfully.", "success"),
    "details_saved": ("Profile details saved.", "success"),
    "no_file": ("No file selected.", "error"),
    "invalid_docx": ("Please upload a .docx file.", "error"),
    "parse_failed": ("Failed to parse resume.", "error"),
    "invalid_json": ("Invalid JSON in one or more fields.", "error"),
}


def _field(label: str, value: Any) -> Div:
    return Div(
        Span(label, cls="profile-field-label"),
        Span(str(value) if value else "—", cls="profile-field-value"),
        cls="profile-field",
    )


def _skills_display(skills: dict[str, Any]) -> Any:
    if not skills:
        return P("No skills added yet.", cls="profile-empty")
    items = []
    for category, vals in skills.items():
        if isinstance(vals, list):
            display = ", ".join(str(v) for v in vals)
        else:
            display = str(vals)
        items.append(
            Div(
                Span(f"{category}:", cls="profile-field-label"),
                Span(display, cls="profile-field-value"),
                cls="profile-field",
            )
        )
    return Div(*items)


def _entry_display(entry: Any) -> Div:
    if isinstance(entry, dict):
        parts = []
        for k, v in entry.items():
            parts.append(
                Div(
                    Span(k, cls="profile-field-label"),
                    Span(str(v), cls="profile-field-value"),
                    cls="profile-field",
                )
            )
        return Div(
            *parts,
            style="margin-bottom:1rem;padding-bottom:1rem;border-bottom:1px solid var(--border);",
        )
    return Div(
        Span(str(entry), cls="profile-field-value"), style="margin-bottom:0.5rem;"
    )


def _list_display(items: list[Any], empty_msg: str) -> Any:
    if not items:
        return P(empty_msg, cls="profile-empty")
    return Div(*[_entry_display(e) for e in items])


def _prefs_display(prefs: dict[str, Any]) -> Any:
    if not prefs:
        return P("No preferences set.", cls="profile-empty")
    return Div(*[_field(k, v) for k, v in prefs.items()])


def register(rt: Any) -> None:  # noqa: C901
    @rt("/profile")
    def get(msg: str = "", error: str = "") -> Any:
        profile = get_profile()
        p = profile or UserProfile(name="")

        # Flash message
        flash: Any = ""
        if msg and msg in _FLASH_MESSAGES:
            text, kind = _FLASH_MESSAGES[msg]
            flash = alert(text, kind)
        elif error and error in _FLASH_MESSAGES:
            text, kind = _FLASH_MESSAGES[error]
            flash = alert(text, kind)

        # ── Basic Info ──────────────────────────────────────────────
        basic_section = Div(
            H3("Basic Information"),
            Form(
                Label("Name", Input(name="name", value=p.name)),
                Label("Email", Input(name="email", type="email", value=p.email)),
                Label("Summary", Textarea(p.summary, name="summary", rows="4")),
                Button("Save Basic Info", type="submit"),
                method="post",
                action="/profile",
            ),
            cls="profile-section",
        )

        # ── Resume ──────────────────────────────────────────────────
        resume_display: Any = ""
        if p.resume_path:
            resume_display = Div(
                Span("📄"),
                Span(p.resume_path, cls="profile-field-value"),
                cls="resume-info",
            )
        resume_section = Div(
            H3("Resume"),
            resume_display,
            Form(
                Label(
                    "Upload .docx resume",
                    Input(type="file", name="resume", accept=".docx"),
                ),
                Button("Upload & Parse Resume", type="submit"),
                method="post",
                action="/profile/resume",
                enctype="multipart/form-data",
            ),
            cls="profile-section",
        )

        # ── Skills ──────────────────────────────────────────────────
        skills_section = Div(
            H3("Skills"),
            _skills_display(p.skills),
            Form(
                Label(
                    "Edit Skills (JSON dict)",
                    Textarea(json.dumps(p.skills, indent=2), name="skills", rows="8"),
                ),
                Button("Save Skills", type="submit"),
                method="post",
                action="/profile/details",
            ),
            cls="profile-section",
        )

        # ── Experience ──────────────────────────────────────────────
        exp_section = Div(
            H3("Experience"),
            _list_display(p.experiences, "No experience entries yet."),
            Form(
                Label(
                    "Edit Experience (JSON list)",
                    Textarea(
                        json.dumps(p.experiences, indent=2),
                        name="experiences",
                        rows="8",
                    ),
                ),
                Button("Save Experience", type="submit"),
                method="post",
                action="/profile/details",
            ),
            cls="profile-section",
        )

        # ── Education ───────────────────────────────────────────────
        edu_section = Div(
            H3("Education"),
            _list_display(p.education, "No education entries yet."),
            Form(
                Label(
                    "Edit Education (JSON list)",
                    Textarea(
                        json.dumps(p.education, indent=2), name="education", rows="8"
                    ),
                ),
                Button("Save Education", type="submit"),
                method="post",
                action="/profile/details",
            ),
            cls="profile-section",
        )

        # ── Preferences ─────────────────────────────────────────────
        prefs_section = Div(
            H3("Preferences"),
            _prefs_display(p.preferences),
            Form(
                Label(
                    "Edit Preferences (JSON dict)",
                    Textarea(
                        json.dumps(p.preferences, indent=2),
                        name="preferences",
                        rows="8",
                    ),
                ),
                Button("Save Preferences", type="submit"),
                method="post",
                action="/profile/details",
            ),
            cls="profile-section",
        )

        # ── Raw JSON (collapsible) ───────────────────────────────────
        profile_dict = {
            "id": p.id,
            "name": p.name,
            "email": p.email,
            "summary": p.summary,
            "skills": p.skills,
            "experiences": p.experiences,
            "education": p.education,
            "preferences": p.preferences,
            "resume_path": p.resume_path,
        }
        raw_section = Div(
            H3("Raw Profile JSON"),
            Details(
                Summary("Show raw JSON"),
                Pre(
                    json.dumps(profile_dict, indent=2, default=str),
                    style="font-size:0.85em;",
                ),
            ),
            cls="profile-section",
        )

        return page(
            H1("Profile"),
            flash,
            basic_section,
            resume_section,
            skills_section,
            exp_section,
            edu_section,
            prefs_section,
            raw_section,
            title="Profile",
        )

    @rt("/profile")
    def post_basic(
        name: str = "", email: str = "", summary: str = ""
    ) -> RedirectResponse:
        profile = get_profile()
        if profile is None:
            profile = UserProfile(name=name, email=email)
        profile.name = name
        profile.email = email
        profile.summary = summary
        save_profile(profile)
        return RedirectResponse("/profile?msg=basic_saved", status_code=303)

    @rt("/profile/resume")
    async def post_resume(request: Request) -> RedirectResponse:
        form = await request.form()
        upload = form.get("resume")
        if upload is None or not hasattr(upload, "read"):
            return RedirectResponse("/profile?error=no_file", status_code=303)

        filename: str = getattr(upload, "filename", "") or ""
        if not filename.lower().endswith(".docx"):
            return RedirectResponse("/profile?error=invalid_docx", status_code=303)

        content: bytes = await upload.read()
        if not content:
            return RedirectResponse("/profile?error=no_file", status_code=303)

        data_dir = Path("data")
        data_dir.mkdir(parents=True, exist_ok=True)
        dest = data_dir / "resume.docx"
        dest.write_bytes(content)

        try:
            parsed = parse_resume(dest)
        except Exception:
            logger.exception("Failed to parse uploaded resume at %s", dest)
            return RedirectResponse("/profile?error=parse_failed", status_code=303)

        profile = get_profile()
        if profile is None:
            profile = UserProfile(name="")

        profile.resume_path = str(dest)

        resume_dict = parsed.to_dict()
        if not profile.name and resume_dict.get("name"):
            profile.name = resume_dict["name"]
        if not profile.summary and resume_dict.get("summary"):
            profile.summary = resume_dict["summary"]

        save_profile(profile)
        return RedirectResponse("/profile?msg=resume_uploaded", status_code=303)

    @rt("/profile/details")
    def post_details(
        skills: str = "",
        experiences: str = "",
        education: str = "",
        preferences: str = "",
    ) -> RedirectResponse:
        profile = get_profile()
        if profile is None:
            profile = UserProfile(name="")

        try:
            if skills:
                parsed_skills = json.loads(skills)
                if not isinstance(parsed_skills, dict):
                    raise ValueError("skills must be a JSON object")
                profile.skills = parsed_skills
            if experiences:
                parsed_exp = json.loads(experiences)
                if not isinstance(parsed_exp, list):
                    raise ValueError("experiences must be a JSON array")
                profile.experiences = parsed_exp
            if education:
                parsed_edu = json.loads(education)
                if not isinstance(parsed_edu, list):
                    raise ValueError("education must be a JSON array")
                profile.education = parsed_edu
            if preferences:
                parsed_prefs = json.loads(preferences)
                if not isinstance(parsed_prefs, dict):
                    raise ValueError("preferences must be a JSON object")
                profile.preferences = parsed_prefs
        except (json.JSONDecodeError, ValueError):
            logger.exception("Invalid JSON submitted to /profile/details")
            return RedirectResponse("/profile?error=invalid_json", status_code=303)

        save_profile(profile)
        return RedirectResponse("/profile?msg=details_saved", status_code=303)
