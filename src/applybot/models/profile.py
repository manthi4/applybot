"""User profile model and Firestore CRUD operations.

``UserProfile`` does **not** inherit :class:`~applybot.models.base.FirestoreModel`:
it is a singleton document (fixed id ``"default"``, replace-on-save, no auto-id)
which does not fit the auto-ID collection shape the base class assumes. It keeps
its own classmethods and reaches the client via ``base.get_db()`` (the module
attribute, not a bound import) so test patching of ``applybot.models.base.get_db``
covers it too.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from applybot.models import base


class ContactInfo(BaseModel):
    """Contact information for the user profile."""

    email: str = ""
    linkedin: str = ""
    phone: str = ""
    github: str = ""


class UserProfile(BaseModel):
    """User profile stored in Firestore as a singleton document."""

    COLLECTION: ClassVar[str] = "profiles"
    # Well-known document id for the singleton profile.
    DOC_ID: ClassVar[str] = "default"

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

    # -- serialization hooks -------------------------------------------------
    @staticmethod
    def _to_doc(profile: UserProfile) -> dict[str, Any]:
        """Convert a UserProfile to a Firestore-compatible dict."""
        return profile.model_dump(exclude={"id"})

    @classmethod
    def _from_doc(cls, doc: Any) -> UserProfile:
        """Convert a Firestore document snapshot to a UserProfile.

        Migrates the legacy flat ``email`` field into the nested ``contact_info``
        object.
        """
        data = doc.to_dict()
        if "email" in data and "contact_info" not in data:
            data["contact_info"] = {"email": data.pop("email")}
        elif "email" in data:
            data.pop("email")
        return cls(id=doc.id, **data)

    # -- CRUD ----------------------------------------------------------------
    @classmethod
    def _ref(cls) -> Any:
        return base.get_db().collection(cls.COLLECTION).document(cls.DOC_ID)

    @classmethod
    def get(cls) -> UserProfile | None:
        """Get the user profile (singleton), or ``None`` if it does not exist."""
        doc = cls._ref().get()
        if not doc.exists:
            return None
        return cls._from_doc(doc)

    def save(self) -> UserProfile:
        """Create or fully replace the user profile."""
        self.updated_at = datetime.now(UTC)
        base.get_db().collection(self.COLLECTION).document(self.DOC_ID).set(
            self._to_doc(self)
        )
        self.id = self.DOC_ID
        return self

    @classmethod
    def update(cls, **fields: Any) -> UserProfile:
        """Update specific fields on the profile.

        Raises ``ValueError`` if no profile exists. Serializes nested Pydantic
        models to dicts for Firestore compatibility, then re-reads and returns.
        """
        fields["updated_at"] = datetime.now(UTC)
        serialized = {
            k: v.model_dump() if isinstance(v, BaseModel) else v
            for k, v in fields.items()
        }
        ref = cls._ref()
        if not ref.get().exists:
            raise ValueError("No profile exists. Create one first.")
        ref.update(serialized)
        return cls._from_doc(ref.get())

    @classmethod
    def delete(cls) -> None:
        """Delete the user profile (for testing)."""
        cls._ref().delete()
