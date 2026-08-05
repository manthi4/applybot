"""Profile page — view and edit user profile."""

from __future__ import annotations

import json
import logging
import tempfile
from pathlib import Path
from typing import Any

from fasthtml.common import (
    H1,
    H3,
    A,
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
from starlette.responses import Response

from applybot.dashboard.components import alert, page
from applybot.dashboard.services.resume_storage import (
    MAX_RESUME_SIZE,
    FileTooLargeError,
    InvalidFileTypeError,
    ResumeStorageError,
    get_resume_download_response,
    store_uploaded_resume,
)
from applybot.dashboard.services.resume_to_profile import resume_to_profile
from applybot.models.profile import ContactInfo, UserProfile

logger = logging.getLogger(__name__)

_FLASH_MESSAGES: dict[str, tuple[str, str]] = {
    "basic_saved": ("Basic profile info saved.", "success"),
    "contact_saved": ("Contact information saved.", "success"),
    "resume_uploaded": ("Resume uploaded and parsed successfully.", "success"),
    "details_saved": ("Profile details saved.", "success"),
    "no_file": ("No file selected.", "error"),
    "invalid_file_type": ("Please upload a .docx, .pdf, or .md file.", "error"),
    "file_too_large": ("Resume file is too large (max 10 MB).", "error"),
    "no_resume": ("No resume file found.", "error"),
    "parse_failed": ("Failed to parse resume.", "error"),
    "invalid_json": ("Invalid JSON in one or more fields.", "error"),
}

_PROFILE_FIELDS = [
    "name",
    "contact_info",
    "summary",
    "skills",
    "experiences",
    "education",
    "preferences",
    "resume_path",
]

_SKILLS_PLACEHOLDER = """\
{
  "Programming": ["Python", "TypeScript"],
  "ML/AI": ["PyTorch", "scikit-learn"],
  "Tools": ["Docker", "Git", "Terraform"]
}"""

_EXPERIENCES_PLACEHOLDER = """\
[
  {
    "title": "ML Engineer",
    "company": "Acme Corp",
    "dates": "2022-2024",
    "description": "Built recommendation systems..."
  }
]"""

_EDUCATION_PLACEHOLDER = """\
[
  {
    "degree": "M.S. Computer Science",
    "school": "MIT",
    "year": "2022"
  }
]"""

_PREFERENCES_PLACEHOLDER = """\
{
  "roles": ["ML Engineer", "Data Scientist"],
  "locations": ["Remote", "New York"],
  "salary_min": 150000
}"""


def _count_filled(profile: UserProfile) -> int:
    """Count how many profile fields have non-empty values."""
    count = 0
    for fld in _PROFILE_FIELDS:
        val = getattr(profile, fld, None)
        if isinstance(val, ContactInfo):
            if any((val.email, val.linkedin, val.phone, val.github)):
                count += 1
        elif isinstance(val, dict | list):
            if val:
                count += 1
        elif val:
            count += 1
    return count


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
    @rt("/profile", methods=["get"])
    def get(msg: str = "", error: str = "") -> Any:
        profile = UserProfile.get()
        p = profile or UserProfile(name="")

        # Flash message
        flash_items: list[Any] = []
        if msg and msg in _FLASH_MESSAGES:
            text, kind = _FLASH_MESSAGES[msg]
            flash_items.append(alert(text, kind))
        elif error and error in _FLASH_MESSAGES:
            text, kind = _FLASH_MESSAGES[error]
            flash_items.append(alert(text, kind))


        flash: Any = Div(*flash_items) if flash_items else ""

        # ── Completeness ───────────────────────────────────────────
        filled = _count_filled(p)
        total = len(_PROFILE_FIELDS)
        pct = int(filled / total * 100) if total else 0
        completeness = Div(
            Div(
                Span(f"{filled}/{total} fields complete", cls="profile-field-value"),
                Span(f"{pct}%", cls="completeness-pct"),
                cls="completeness-header",
            ),
            Div(
                Div(style=f"width:{pct}%;", cls="completeness-fill"),
                cls="completeness-bar",
            ),
            cls="profile-completeness",
        )

        # ── Basic Info ──────────────────────────────────────────────
        basic_section = Div(
            H3("Basic Information"),
            Form(
                Label("Name", Input(name="name", value=p.name)),
                Label("Summary", Textarea(p.summary, name="summary", rows="4")),
                Button("Save Basic Info", type="submit"),
                method="post",
                action="/profile",
            ),
            cls="profile-section",
        )

        # ── Contact Information ─────────────────────────────────────
        ci = p.contact_info
        contact_section = Div(
            H3("Contact Information"),
            Form(
                Label("Email", Input(name="email", type="email", value=ci.email)),
                Label(
                    "LinkedIn",
                    Input(
                        name="linkedin",
                        value=ci.linkedin,
                        placeholder="https://linkedin.com/in/yourname",
                    ),
                ),
                Label("Phone", Input(name="phone", type="tel", value=ci.phone)),
                Label(
                    "GitHub",
                    Input(
                        name="github",
                        value=ci.github,
                        placeholder="https://github.com/yourname",
                    ),
                ),
                Button("Save Contact Info", type="submit"),
                method="post",
                action="/profile/contact",
            ),
            cls="profile-section",
        )

        # ── Resume ──────────────────────────────────────────────────
        resume_display: Any = ""
        if p.resume_path:
            resume_display = Div(
                Span("📄"),
                Span(p.resume_path, cls="profile-field-value"),
                A("Download", href="/profile/resume", cls="resume-download"),
                cls="resume-info",
            )
        resume_section = Div(
            H3("Resume"),
            resume_display,
            Form(
                Label(
                    "Upload resume (.docx, .pdf, or .md)",
                    Input(type="file", name="resume", accept=".docx,.pdf,.md"),
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
            Details(
                Summary("Edit Skills"),
                Form(
                    Textarea(
                        json.dumps(p.skills, indent=2) if p.skills else "",
                        name="skills",
                        rows="8",
                        placeholder=_SKILLS_PLACEHOLDER,
                    ),
                    Button("Save Skills", type="submit"),
                    method="post",
                    action="/profile/details",
                ),
            ),
            cls="profile-section",
        )

        # ── Experience ──────────────────────────────────────────────
        exp_section = Div(
            H3("Experience"),
            _list_display(p.experiences, "No experience entries yet."),
            Details(
                Summary("Edit Experience"),
                Form(
                    Textarea(
                        json.dumps(p.experiences, indent=2) if p.experiences else "",
                        name="experiences",
                        rows="8",
                        placeholder=_EXPERIENCES_PLACEHOLDER,
                    ),
                    Button("Save Experience", type="submit"),
                    method="post",
                    action="/profile/details",
                ),
            ),
            cls="profile-section",
        )

        # ── Education ───────────────────────────────────────────────
        edu_section = Div(
            H3("Education"),
            _list_display(p.education, "No education entries yet."),
            Details(
                Summary("Edit Education"),
                Form(
                    Textarea(
                        json.dumps(p.education, indent=2) if p.education else "",
                        name="education",
                        rows="8",
                        placeholder=_EDUCATION_PLACEHOLDER,
                    ),
                    Button("Save Education", type="submit"),
                    method="post",
                    action="/profile/details",
                ),
            ),
            cls="profile-section",
        )

        # ── Preferences ─────────────────────────────────────────────
        prefs_section = Div(
            H3("Preferences"),
            _prefs_display(p.preferences),
            Details(
                Summary("Edit Preferences"),
                Form(
                    Textarea(
                        json.dumps(p.preferences, indent=2) if p.preferences else "",
                        name="preferences",
                        rows="8",
                        placeholder=_PREFERENCES_PLACEHOLDER,
                    ),
                    Button("Save Preferences", type="submit"),
                    method="post",
                    action="/profile/details",
                ),
            ),
            cls="profile-section",
        )

        # ── Raw JSON (collapsible) ───────────────────────────────────
        profile_dict = {
            "id": p.id,
            "name": p.name,
            "contact_info": p.contact_info.model_dump(),
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
            completeness,
            basic_section,
            contact_section,
            resume_section,
            skills_section,
            exp_section,
            edu_section,
            prefs_section,
            raw_section,
            title="Profile",
        )

    @rt("/profile", methods=["post"])
    def post_basic(name: str = "", summary: str = "") -> RedirectResponse:
        profile = UserProfile.get()
        if profile is None:
            profile = UserProfile(name=name)
        profile.name = name
        profile.summary = summary
        profile.save()
        return RedirectResponse("/profile?msg=basic_saved", status_code=303)

    @rt("/profile/contact", methods=["post"])
    def post_contact(
        email: str = "",
        linkedin: str = "",
        phone: str = "",
        github: str = "",
    ) -> RedirectResponse:
        profile = UserProfile.get()
        if profile is None:
            profile = UserProfile(name="")
        profile.contact_info = ContactInfo(
            email=email.strip(),
            linkedin=linkedin.strip(),
            phone=phone.strip(),
            github=github.strip(),
        )
        profile.save()
        return RedirectResponse("/profile?msg=contact_saved", status_code=303)

    @rt("/profile/resume", methods=["get"])
    def get_resume() -> Response:
        profile = UserProfile.get()
        if profile is not None:
            response = get_resume_download_response(profile.resume_path)
            if response is not None:
                return response
        return RedirectResponse("/profile?error=no_resume", status_code=303)

    @rt("/profile/resume", methods=["post"])
    async def post_resume(request: Request) -> RedirectResponse:
        form = await request.form()
        upload = form.get("resume")
        if upload is None or not hasattr(upload, "read"):
            return RedirectResponse("/profile?error=no_file", status_code=303)

        # Cap the read one byte over the limit so the service can detect oversize.
        content: bytes = await upload.read(MAX_RESUME_SIZE + 1)
        if not content:
            return RedirectResponse("/profile?error=no_file", status_code=303)

        profile = UserProfile.get()
        if profile is None:
            profile = UserProfile(name="")

        filename = getattr(upload, "filename", "") or ""

        # 1. Save the resume to storage (independent of the profile). The
        #    service returns the storage object name; the page records it on
        #    the profile and persists, so resume_path survives even if the
        #    enrichment step below fails.
        try:
            object_name = store_uploaded_resume(content, filename)
        except InvalidFileTypeError:
            return RedirectResponse("/profile?error=invalid_file_type", status_code=303)
        except FileTooLargeError:
            return RedirectResponse("/profile?error=file_too_large", status_code=303)
        except ResumeStorageError:
            logger.exception("Unexpected resume storage failure")
            return RedirectResponse("/profile?error=parse_failed", status_code=303)

        profile.resume_path = object_name
        # 2. Enrich the profile from the resume (separate service, blocking LLM).
        #    Spool the uploaded bytes to a temp file for the parser; the two
        #    services share no state beyond the profile object the page passes.
        ext = Path(filename).suffix.lower()
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        try:
            updated_profile = resume_to_profile(tmp_path, profile)
            updated_profile.resume_path = object_name
            updated_profile.save()
        except (ValueError, ImportError):
            profile.save()  # preserve the uploaded resume even if parsing fails
            logger.exception("Failed to parse uploaded resume")
            return RedirectResponse("/profile?error=parse_failed", status_code=303)
        finally:
            tmp_path.unlink(missing_ok=True)

        return RedirectResponse("/profile?msg=resume_uploaded", status_code=303)

    @rt("/profile/details", methods=["post"])
    def post_details(
        skills: str = "",
        experiences: str = "",
        education: str = "",
        preferences: str = "",
    ) -> RedirectResponse:
        profile = UserProfile.get()
        if profile is None:
            profile = UserProfile(name="")

        try:
            if skills.strip():
                parsed_skills = json.loads(skills)
                if not isinstance(parsed_skills, dict):
                    raise ValueError("skills must be a JSON object")
                profile.skills = parsed_skills
            if experiences.strip():
                parsed_exp = json.loads(experiences)
                if not isinstance(parsed_exp, list):
                    raise ValueError("experiences must be a JSON array")
                profile.experiences = parsed_exp
            if education.strip():
                parsed_edu = json.loads(education)
                if not isinstance(parsed_edu, list):
                    raise ValueError("education must be a JSON array")
                profile.education = parsed_edu
            if preferences.strip():
                parsed_prefs = json.loads(preferences)
                if not isinstance(parsed_prefs, dict):
                    raise ValueError("preferences must be a JSON object")
                profile.preferences = parsed_prefs
        except (json.JSONDecodeError, ValueError):
            logger.exception("Invalid JSON submitted to /profile/details")
            return RedirectResponse("/profile?error=invalid_json", status_code=303)

        profile.save()
        return RedirectResponse("/profile?msg=details_saved", status_code=303)
