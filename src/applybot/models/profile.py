"""User profile model and Firestore CRUD operations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from applybot.models.base import get_db

COLLECTION = "profiles"

# We use a well-known document ID for the singleton profile
PROFILE_DOC_ID = "default"


class ContactInfo(BaseModel):
    """Contact information for the user profile."""

    email: str = ""
    linkedin: str = ""
    phone: str = ""
    github: str = ""


class UserProfile(BaseModel):
    """User profile stored in Firestore."""

    id: str = ""
    name: str
    contact_info: ContactInfo = Field(default_factory=ContactInfo)
    summary: str = ""
    skills: dict[str, Any] = Field(default_factory=dict)
    experiences: list[Any] = Field(default_factory=list)
    education: list[Any] = Field(default_factory=list)
    preferences: dict[str, Any] = Field(default_factory=dict)
    resume_path: str = ""
    enrichment_warning: str = ""
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def __repr__(self) -> str:
        return f"<UserProfile {self.id}: {self.name}>"


def _profile_to_doc(profile: UserProfile) -> dict[str, Any]:
    """Convert a UserProfile to a Firestore-compatible dict."""
    return profile.model_dump(exclude={"id"})


def _doc_to_profile(doc: Any) -> UserProfile:
    """Convert a Firestore document snapshot to a UserProfile."""
    data = doc.to_dict()
    # Migrate legacy flat 'email' field into the nested contact_info object.
    if "email" in data and "contact_info" not in data:
        data["contact_info"] = {"email": data.pop("email")}
    elif "email" in data:
        data.pop("email")
    return UserProfile(id=doc.id, **data)


def get_profile() -> UserProfile | None:
    """Get the user profile (singleton)."""
    doc = get_db().collection(COLLECTION).document(PROFILE_DOC_ID).get()
    if not doc.exists:
        return None
    return _doc_to_profile(doc)


def save_profile(profile: UserProfile) -> UserProfile:
    """Create or fully replace the user profile."""
    profile.updated_at = datetime.now(UTC)
    data = _profile_to_doc(profile)
    get_db().collection(COLLECTION).document(PROFILE_DOC_ID).set(data)
    profile.id = PROFILE_DOC_ID
    return profile


def update_profile_fields(**fields: Any) -> UserProfile:
    """Update specific fields on the profile. Raises ValueError if no profile exists."""
    fields["updated_at"] = datetime.now(UTC)
    # Serialize any nested Pydantic models to dicts for Firestore compatibility.
    serialized = {
        k: v.model_dump() if isinstance(v, BaseModel) else v for k, v in fields.items()
    }
    ref = get_db().collection(COLLECTION).document(PROFILE_DOC_ID)
    doc = ref.get()
    if not doc.exists:
        raise ValueError("No profile exists. Create one first.")
    ref.update(serialized)
    # Re-read and return
    updated_doc = ref.get()
    return _doc_to_profile(updated_doc)


def delete_profile() -> None:
    """Delete the user profile (for testing)."""
    get_db().collection(COLLECTION).document(PROFILE_DOC_ID).delete()
