"""Firestore client management and the base model for Firestore-backed documents.

This module provides two things:

* :func:`get_db` — a process-wide cached Firestore client.
* :class:`FirestoreModel` — a :class:`pydantic.BaseModel` mixin that gives
  subclasses document-level CRUD (``get``/``save``/``update``/
  ``count_by_status``) against a single Firestore collection of auto-ID
  documents.
"""

from __future__ import annotations

from functools import lru_cache
from os import environ
from typing import Any, ClassVar, Self

from google.cloud.firestore_v1 import Client
from pydantic import BaseModel


@lru_cache(maxsize=1)
def get_db() -> Client:
    """Return the Firestore client singleton, lazily built and cached.

    The client is cached for the process lifetime via :func:`functools.lru_cache`;
    every subsequent call returns the same :class:`~google.cloud.firestore_v1.Client`
    without re-resolving credentials or project. Construction honors the
    standard Firestore environment:

    * ``FIRESTORE_EMULATOR_HOST`` — when set (e.g. ``localhost:8080``) the client
    * ``GCP_PROJECT_ID`` env var — the project id passed to the client.
    * Otherwise Application Default Credentials are used.

    To force re-initialization (e.g. between tests that swap the emulator in
    and out), call ``get_db.cache_clear()``.
    """
    kwargs: dict[str, Any] = {}
    project_id = environ.get("GCP_PROJECT_ID")
    if project_id:
        kwargs["project"] = project_id
    return Client(**kwargs)


def init_db() -> None:
    """Eagerly construct the Firestore client.

    Firestore is schema-less, so there is no migration to run. This forces
    client construction (and thus project/credential resolution) at startup so
    misconfiguration surfaces immediately rather than on the first query. It
    does **not** perform a network round-trip — the :class:`Client` is lazy and
    only contacts Firestore on the first request.
    """
    get_db()


class FirestoreModel(BaseModel):
    """Pydantic model backed by a Firestore collection of auto-ID documents.

    Subclasses declare two class vars:

    * ``COLLECTION`` — the Firestore collection name.
    * ``ENUM_FIELDS`` — model field names whose enum values must be serialized
      to plain strings on write (Firestore stores enums as their ``.value``).

    Override :meth:`to_doc` / :meth:`from_doc` for any extra serialization or
    legacy-data migration specific to a subclass; be sure to call ``super()``
    so the base enum coercion and ``id`` handling are preserved.
    """

    COLLECTION: ClassVar[str] = ""
    ENUM_FIELDS: ClassVar[tuple[str, ...]] = ()

    id: str = ""

    # -- serialization hooks -------------------------------------------------
    def to_doc(self) -> dict[str, Any]:
        """Serialize this document to a Firestore-compatible dict.

        Drops ``id`` (Firestore owns document ids) and coerces every field in
        ``ENUM_FIELDS`` from its enum member to its plain ``.value`` string.
        """
        data = self.model_dump(exclude={"id"})
        for field in self.ENUM_FIELDS:
            value = data.get(field)
            if hasattr(value, "value"):
                data[field] = getattr(value, "value")
        return data

    @classmethod
    def from_doc(cls, doc: Any) -> Self:
        """Build an instance from a Firestore document snapshot."""
        return cls(id=doc.id, **doc.to_dict())

    # -- CRUD ----------------------------------------------------------------
    @classmethod
    def _collection(cls) -> Any:
        return get_db().collection(cls.COLLECTION)

    @classmethod
    def get(cls, doc_id: str) -> Self | None:
        """Fetch a document by id, or ``None`` if it does not exist."""
        doc = cls._collection().document(doc_id).get()
        if not doc.exists:
            return None
        return cls.from_doc(doc)

    def save(self) -> Self:
        """Insert this document and populate ``self.id`` with the generated id.

        This is insert-only; use :meth:`update` to mutate an existing document.
        """
        _, ref = self._collection().add(self.to_doc())
        self.id = ref.id
        return self

    @classmethod
    def update(cls, doc_id: str, **fields: Any) -> None:
        """Patch specific fields on an existing document.

        Enum-valued kwargs in ``ENUM_FIELDS`` are coerced to their ``.value``.
        """
        for field in cls.ENUM_FIELDS:
            value = fields.get(field)
            if hasattr(value, "value"):
                fields[field] = getattr(value, "value")
        cls._collection().document(doc_id).update(fields)

    @classmethod
    def count_by_status(cls) -> dict[str, int]:
        """Tally documents grouped by their ``status`` field, plus a ``total``."""
        counts: dict[str, int] = {}
        total = 0
        for doc in cls._collection().select(["status"]).stream():
            status = doc.to_dict().get("status", "unknown")
            counts[status] = counts.get(status, 0) + 1
            total += 1
        counts["total"] = total
        return counts
