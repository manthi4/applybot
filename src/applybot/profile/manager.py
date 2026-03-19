"""Profile manager — CRUD operations for the user profile."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from applybot.models.base import get_session
from applybot.models.profile import UserProfile

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")


class ProfileManager:
    """Load, save, and query the user profile stored in the database."""

    def get_profile(self) -> UserProfile | None:
        """Return the first (and only) user profile, or None."""
        with get_session() as session:
            return session.query(UserProfile).first()

    def get_or_create_profile(self, name: str = "", email: str = "") -> UserProfile:
        """Return existing profile or create a blank one."""
        profile = self.get_profile()
        if profile is not None:
            return profile
        profile = UserProfile(name=name, email=email)
        with get_session() as session:
            session.add(profile)
            session.commit()
            session.refresh(profile)
            return profile

    def update_profile(self, **kwargs: Any) -> UserProfile:
        """Update profile fields. Accepts any UserProfile column name."""
        with get_session() as session:
            profile = session.query(UserProfile).first()
            if profile is None:
                raise ValueError("No profile exists. Create one first.")
            for key, value in kwargs.items():
                if not hasattr(profile, key):
                    raise ValueError(f"Unknown profile field: {key}")
                setattr(profile, key, value)
            session.commit()
            session.refresh(profile)
            return profile

    def get_skills(self) -> dict[str, Any]:
        """Return the skills dict from the profile."""
        profile = self.get_profile()
        if profile is None:
            return {}
        return profile.skills or {}

    def get_experiences(self) -> list[Any]:
        """Return the experiences list from the profile."""
        profile = self.get_profile()
        if profile is None:
            return []
        return profile.experiences or []

    def export_profile_json(self, path: Path | None = None) -> Path:
        """Export the profile to a JSON file for easy editing."""
        profile = self.get_profile()
        if profile is None:
            raise ValueError("No profile exists.")
        path = path or DATA_DIR / "profile.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "name": profile.name,
            "email": profile.email,
            "summary": profile.summary,
            "skills": profile.skills,
            "experiences": profile.experiences,
            "education": profile.education,
            "preferences": profile.preferences,
            "resume_path": profile.resume_path,
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info("Profile exported to %s", path)
        return path

    def import_profile_json(self, path: Path | None = None) -> UserProfile:
        """Import profile from a JSON file, creating or updating the DB record."""
        path = path or DATA_DIR / "profile.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        profile = self.get_profile()
        with get_session() as session:
            if profile is None:
                profile = UserProfile(**data)
                session.add(profile)
            else:
                for key, value in data.items():
                    if hasattr(profile, key):
                        setattr(profile, key, value)
                session.merge(profile)
            session.commit()
            session.refresh(profile)
            return profile
