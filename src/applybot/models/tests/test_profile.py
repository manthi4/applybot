"""Tests for the UserProfile model and Firestore CRUD operations (profile.py)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from applybot.models.profile import (
    ContactInfo,
    UserProfile,
)

PROFILES_COLLECTION = "profiles"


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------


def _make_profile(**overrides: Any) -> UserProfile:
    defaults: dict[str, Any] = {
        "name": "Test User",
        "contact_info": ContactInfo(
            email="test@example.com",
            linkedin="https://linkedin.com/in/test",
            phone="555-1234",
            github="https://github.com/test",
        ),
        "summary": "ML engineer with 5 years experience",
        "skills": {"technical": ["Python", "PyTorch", "ROS"]},
        "experiences": [{"title": "ML Engineer", "company": "TechCo"}],
        "education": [{"degree": "BS CS", "school": "University"}],
        "preferences": {"remote": True, "locations": ["US", "EU"]},
    }
    defaults.update(overrides)
    return UserProfile(**defaults)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class TestContactInfoModel:
    def test_defaults(self):
        info = ContactInfo()
        assert info.email == ""
        assert info.linkedin == ""
        assert info.phone == ""
        assert info.github == ""


class TestUserProfileModel:
    def test_defaults(self):
        profile = UserProfile(name="Someone")
        assert profile.id == ""
        assert profile.name == "Someone"
        assert isinstance(profile.contact_info, ContactInfo)
        assert profile.summary == ""
        assert profile.skills == {}
        assert profile.experiences == []
        assert profile.education == []
        assert profile.preferences == {}
        assert profile.resume_path == ""
        assert isinstance(profile.updated_at, datetime)

    def test_repr(self):
        profile = UserProfile(name="Alice")
        assert repr(profile) == "<UserProfile : Alice>"


# ---------------------------------------------------------------------------
# Serialization / legacy migration
# ---------------------------------------------------------------------------


class _StubDoc:
    def __init__(self, data: dict[str, Any], doc_id: str = "stub-id") -> None:
        self.id = doc_id
        self._data = data

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)


class TestProfileSerialization:
    def test_round_trip(self):
        profile = _make_profile()
        roundtripped = UserProfile._from_doc(_StubDoc(UserProfile._to_doc(profile)))
        assert roundtripped.name == profile.name
        assert roundtripped.contact_info.email == "test@example.com"
        assert roundtripped.skills["technical"] == ["Python", "PyTorch", "ROS"]
        assert roundtripped.preferences["remote"] is True

    def test_legacy_flat_email_migrated_to_contact_info(self):
        """When a legacy doc has flat `email` but no `contact_info`, the email
        is migrated into a new nested `contact_info.email` field."""
        legacy = {
            "name": "Legacy User",
            "email": "legacy@example.com",
            "summary": "",
            "skills": {},
            "experiences": [],
            "education": [],
            "preferences": {},
            "resume_path": "",
            "updated_at": datetime.now(UTC),
        }
        profile = UserProfile._from_doc(_StubDoc(legacy))
        assert profile.contact_info.email == "legacy@example.com"

    def test_nested_contact_info_wins_over_legacy_flat_email(self):
        """When both `email` and `contact_info` exist, the nested
        `contact_info.email` takes precedence over the legacy flat `email`."""
        legacy = {
            "name": "Legacy User",
            "email": "stale@example.com",
            "contact_info": {"email": "nested@example.com"},
            "summary": "",
            "skills": {},
            "experiences": [],
            "education": [],
            "preferences": {},
            "resume_path": "",
            "updated_at": datetime.now(UTC),
        }
        profile = UserProfile._from_doc(_StubDoc(legacy))
        assert profile.contact_info.email == "nested@example.com"


# ---------------------------------------------------------------------------
# Singleton CRUD
# ---------------------------------------------------------------------------


class TestProfileCRUD:
    def test_get_when_none(self):
        assert UserProfile.get() is None

    def test_save_create_and_id(self):
        profile = _make_profile()
        assert profile.id == ""
        saved = profile.save()
        assert saved.id == UserProfile.DOC_ID

    def test_save_round_trip(self):
        _make_profile().save()
        fetched = UserProfile.get()
        assert fetched is not None
        assert fetched.name == "Test User"
        assert fetched.contact_info.email == "test@example.com"

    def test_save_refreshes_updated_at(self):
        profile = _make_profile()
        pre_save_ts = profile.updated_at
        profile.save()
        fetched = UserProfile.get()
        assert fetched is not None
        assert fetched.updated_at > pre_save_ts

    def test_save_full_replace(self):
        _make_profile(name="Original").save()
        _make_profile(name="Replaced").save()
        fetched = UserProfile.get()
        assert fetched is not None
        assert fetched.name == "Replaced"


# ---------------------------------------------------------------------------
# UserProfile.update
# ---------------------------------------------------------------------------


class TestUserProfileUpdate:
    def test_updates_fields_and_rereads(self):
        _make_profile().save()
        updated = UserProfile.update(summary="New summary")
        assert updated.summary == "New summary"
        # Confirm persisted
        persisted = UserProfile.get()
        assert persisted is not None
        assert persisted.summary == "New summary"

    def test_sets_updated_at(self):
        _make_profile().save()
        before = UserProfile.get()
        assert before is not None
        before_ts = before.updated_at
        UserProfile.update(summary="x")
        after = UserProfile.get()
        assert after is not None
        assert after.updated_at >= before_ts

    def test_serializes_nested_basemodel(self):
        """Passing a ContactInfo (a BaseModel) must be serialized to a dict."""
        _make_profile().save()
        new_contact = ContactInfo(
            email="new@example.com", github="https://github.com/new"
        )
        updated = UserProfile.update(contact_info=new_contact)
        assert updated.contact_info.email == "new@example.com"
        assert updated.contact_info.github == "https://github.com/new"

    def test_raises_when_no_profile_exists(self):
        with pytest.raises(ValueError, match="No profile exists"):
            UserProfile.update(summary="x")


# ---------------------------------------------------------------------------
# UserProfile.delete
# ---------------------------------------------------------------------------


class TestUserProfileDelete:
    def test_deletes_existing(self):
        _make_profile().save()
        UserProfile.delete()
        assert UserProfile.get() is None

    def test_idempotent_on_missing(self):
        # Should not raise when the profile doesn't exist.
        UserProfile.delete()
        assert UserProfile.get() is None
