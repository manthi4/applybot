"""Profile page — view and edit user profile."""

from __future__ import annotations

import asyncio
import json
import logging
import re
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
from applybot.models.profile import ContactInfo, UserProfile, get_profile, save_profile
from applybot.profile.enrichment import (
    enrich_profile_with_llm_async,
    extract_raw_resume_text,
)
from applybot.profile.resume import ResumeData, parse_resume
from applybot.storage import file_exists, get_download_response, upload_file

logger = logging.getLogger(__name__)

_MAX_RESUME_SIZE = 10 * 1024 * 1024  # 10 MB

_ALLOWED_EXTENSIONS = {".docx", ".pdf", ".md"}

_MIME_TYPES = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".pdf": "application/pdf",
    ".md": "text/markdown",
}

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


def _map_resume_to_profile(parsed: ResumeData, profile: UserProfile) -> None:
    """Map parsed resume sections to profile fields when they're empty."""
    resume_dict = parsed.to_dict()

    if not profile.name and resume_dict.get("name"):
        profile.name = resume_dict["name"]
    if not profile.summary and resume_dict.get("summary"):
        profile.summary = resume_dict["summary"]

    # Best-effort: extract email from the raw contact_info string produced by the parser.
    # The LLM enrichment step will do a more thorough extraction of all contact fields.
    raw_contact = resume_dict.get("contact_info", "")
    if raw_contact and not profile.contact_info.email:
        email_match = re.search(
            r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", raw_contact
        )
        if email_match:
            profile.contact_info.email = email_match.group(0)

    for section in parsed.sections:
        heading_lower = section.heading.lower()

        if any(
            kw in heading_lower
            for kw in (
                "skill",
                "technologies",
                "tools",
                "tech stack",
                "competenc",
                "language",
                "programming",
            )
        ):
            if profile.skills is None:
                profile.skills = {}
            profile.skills[section.heading] = section.items
        elif any(
            kw in heading_lower
            for kw in ("experience", "employment", "work history", "career")
        ):
            new_entries = [
                {"section": section.heading, "details": item} for item in section.items
            ]
            if profile.experiences is None:
                profile.experiences = new_entries
            else:
                profile.experiences.extend(new_entries)
        elif any(
            kw in heading_lower
            for kw in ("education", "academic", "degree", "university", "school")
        ):
            new_entries = [
                {"section": section.heading, "details": item} for item in section.items
            ]
            if profile.education is None:
                profile.education = new_entries
            else:
                profile.education.extend(new_entries)


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
        profile = get_profile()
        p = profile or UserProfile(name="")

        # Flash message
        flash_items: list[Any] = []
        if msg and msg in _FLASH_MESSAGES:
            text, kind = _FLASH_MESSAGES[msg]
            flash_items.append(alert(text, kind))
        elif error and error in _FLASH_MESSAGES:
            text, kind = _FLASH_MESSAGES[error]
            flash_items.append(alert(text, kind))

        if p.enrichment_warning:
            flash_items.append(alert(p.enrichment_warning, "error"))

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
        profile = get_profile()
        if profile is None:
            profile = UserProfile(name=name)
        profile.name = name
        profile.summary = summary
        save_profile(profile)
        return RedirectResponse("/profile?msg=basic_saved", status_code=303)

    @rt("/profile/contact", methods=["post"])
    def post_contact(
        email: str = "",
        linkedin: str = "",
        phone: str = "",
        github: str = "",
    ) -> RedirectResponse:
        profile = get_profile()
        if profile is None:
            profile = UserProfile(name="")
        profile.contact_info = ContactInfo(
            email=email.strip(),
            linkedin=linkedin.strip(),
            phone=phone.strip(),
            github=github.strip(),
        )
        save_profile(profile)
        return RedirectResponse("/profile?msg=contact_saved", status_code=303)

    @rt("/profile/resume", methods=["get"])
    def get_resume() -> Response:
        profile = get_profile()
        object_name = profile.resume_path if profile and profile.resume_path else None
        if object_name and file_exists(object_name):
            return get_download_response(object_name, Path(object_name).name)
        # Legacy fallback: check old local paths for backwards compat
        for ext in _ALLOWED_EXTENSIONS:
            legacy_name = f"resumes/resume{ext}"
            if file_exists(legacy_name):
                return get_download_response(legacy_name, f"resume{ext}")
        return RedirectResponse("/profile?error=no_resume", status_code=303)

    @rt("/profile/resume", methods=["post"])
    async def post_resume(request: Request) -> RedirectResponse:
        form = await request.form()
        upload = form.get("resume")
        if upload is None or not hasattr(upload, "read"):
            return RedirectResponse("/profile?error=no_file", status_code=303)

        filename: str = getattr(upload, "filename", "") or ""
        ext = Path(filename).suffix.lower()
        if ext not in _ALLOWED_EXTENSIONS:
            return RedirectResponse("/profile?error=invalid_file_type", status_code=303)

        content: bytes = await upload.read(_MAX_RESUME_SIZE + 1)
        if not content:
            return RedirectResponse("/profile?error=no_file", status_code=303)
        if len(content) > _MAX_RESUME_SIZE:
            return RedirectResponse("/profile?error=file_too_large", status_code=303)

        # Upload to GCS (or local fallback)
        object_name = f"resumes/resume{ext}"
        upload_file(content, object_name)

        # parse_resume / extract_raw_resume_text need a local Path, so use a temp file
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        try:
            try:
                parsed = parse_resume(tmp_path)
            except Exception:
                logger.exception("Failed to parse uploaded resume")
                return RedirectResponse("/profile?error=parse_failed", status_code=303)

            profile = get_profile()
            if profile is None:
                profile = UserProfile(name="")

            profile.resume_path = object_name
            profile.enrichment_warning = ""

            _map_resume_to_profile(parsed, profile)

            save_profile(profile)

            # Kick off LLM enrichment in the background — won't delay the response.
            # Raw file text is used (not the heuristic-parsed JSON) so the LLM sees
            # everything, including sections the keyword matcher may have missed.
            resume_text = extract_raw_resume_text(tmp_path)
            asyncio.create_task(enrich_profile_with_llm_async(profile, resume_text))
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
        profile = get_profile()
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

        save_profile(profile)
        return RedirectResponse("/profile?msg=details_saved", status_code=303)
