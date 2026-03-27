"""Profile manager — CRUD operations for the user profile."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from applybot.models.profile import (
    UserProfile,
    save_profile,
    update_profile_fields,
)
from applybot.models.profile import (
    get_profile as _get_profile,
)

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")


class ProfileManager:
    """Load, save, and query the user profile stored in Firestore."""

    def get_profile(self) -> UserProfile | None:
        """Return the user profile, or None."""
        return _get_profile()

    def get_or_create_profile(self, name: str = "", email: str = "") -> UserProfile:
        """Return existing profile or create a blank one."""
        profile = _get_profile()
        if profile is not None:
            return profile
        profile = UserProfile(name=name, email=email)
        return save_profile(profile)

    def update_profile(self, **kwargs: Any) -> UserProfile:
        """Update profile fields. Accepts any UserProfile field name."""
        # Validate field names
        valid_fields = set(UserProfile.model_fields.keys()) - {"id"}
        for key in kwargs:
            if key not in valid_fields:
                raise ValueError(f"Unknown profile field: {key}")
        return update_profile_fields(**kwargs)

    def get_skills(self) -> dict[str, Any]:
        """Return the skills dict from the profile."""
        profile = _get_profile()
        if profile is None:
            return {}
        return profile.skills or {}

    def get_experiences(self) -> list[Any]:
        """Return the experiences list from the profile."""
        profile = _get_profile()
        if profile is None:
            return []
        return profile.experiences or []

    def export_profile_json(self, path: Path | None = None) -> Path:
        """Export the profile to a JSON file for easy editing."""
        profile = _get_profile()
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
        path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        logger.info("Profile exported to %s", path)
        return path

    def import_profile_json(self, path: Path | None = None) -> UserProfile:
        """Import profile from a JSON file, creating or updating the DB record."""
        path = path or DATA_DIR / "profile.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        profile = _get_profile()
        if profile is None:
            profile = UserProfile(**data)
        else:
            for key, value in data.items():
                if hasattr(profile, key) and key != "id":
                    setattr(profile, key, value)
        return save_profile(profile)
