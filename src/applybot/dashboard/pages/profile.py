"""Profile page — view and edit user profile."""

from __future__ import annotations

import json
from typing import Any

from fasthtml.common import (
    H1,
    Button,
    Details,
    Form,
    Input,
    Label,
    Pre,
    RedirectResponse,
    Summary,
    Textarea,
)

from applybot.dashboard.components import page
from applybot.models.base import get_session
from applybot.models.profile import UserProfile


def register(rt: Any) -> None:
    @rt("/profile")
    def get() -> tuple[object, ...]:
        with get_session() as session:
            profile = session.query(UserProfile).first()

        name_val = profile.name if profile else ""
        email_val = profile.email if profile else ""
        summary_val = profile.summary if profile else ""

        form = Form(
            Label("Name", Input(name="name", value=name_val)),
            Label("Email", Input(name="email", type="email", value=email_val)),
            Label("Summary", Textarea(summary_val, name="summary", rows="4")),
            Button("Save Profile", type="submit"),
            method="post",
            action="/profile",
        )

        full_data = ""
        if profile:
            profile_dict = {
                "id": profile.id,
                "name": profile.name,
                "email": profile.email,
                "summary": profile.summary,
                "skills": profile.skills,
                "experiences": profile.experiences,
                "education": profile.education,
                "preferences": profile.preferences,
                "resume_path": profile.resume_path,
            }
            full_data = Details(
                Summary("Full Profile Data"),
                Pre(
                    json.dumps(profile_dict, indent=2, default=str),
                    style="font-size:0.85em;",
                ),
            )

        return page(H1("Profile"), form, full_data, title="Profile")

    @rt("/profile")
    def post(name: str = "", email: str = "", summary: str = "") -> RedirectResponse:
        with get_session() as session:
            profile = session.query(UserProfile).first()
            if profile is None:
                profile = UserProfile(name=name, email=email)
                session.add(profile)
            profile.name = name
            profile.email = email
            profile.summary = summary
            session.commit()
        return RedirectResponse("/profile", status_code=303)
