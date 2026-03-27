"""Shared test fixtures — mock Firestore client for all tests.

Provides a complete in-memory mock that replaces google.cloud.firestore_v1
at the sys.modules level, so tests can run even when the real
google-cloud-firestore package is not installed (e.g. Windows ARM64
where grpcio has no binary wheels).
"""

from __future__ import annotations

import sys
import uuid
from datetime import UTC, datetime
from typing import Any
from unittest.mock import MagicMock

import pytest

# ---------------------------------------------------------------------------
# Mock Firestore objects
# ---------------------------------------------------------------------------


class MockFieldFilter:
    """Mock of google.cloud.firestore_v1.base_query.FieldFilter."""

    def __init__(self, field_path: str, op_string: str, value: Any):
        self.field_path = field_path
        self.op_string = op_string
        self.value = value


class MockDocumentSnapshot:
    """Simulates a Firestore DocumentSnapshot."""

    def __init__(self, doc_id: str, data: dict[str, Any] | None, exists: bool = True):
        self.id = doc_id
        self._data = data or {}
        self.exists = exists

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)


class MockDocumentReference:
    """Simulates a Firestore DocumentReference."""

    def __init__(self, collection: MockCollectionReference, doc_id: str):
        self._collection = collection
        self.id = doc_id

    def get(self) -> MockDocumentSnapshot:
        data = self._collection._store.get(self.id)
        if data is None:
            return MockDocumentSnapshot(self.id, None, exists=False)
        return MockDocumentSnapshot(self.id, data)

    def set(self, data: dict[str, Any]) -> None:
        self._collection._store[self.id] = dict(data)

    def update(self, fields: dict[str, Any]) -> None:
        if self.id not in self._collection._store:
            raise Exception(f"Document {self.id} not found")
        self._collection._store[self.id].update(fields)

    def delete(self) -> None:
        self._collection._store.pop(self.id, None)


class MockQuery:
    """Simulates a Firestore Query with chaining."""

    def __init__(self, docs: list[tuple[str, dict[str, Any]]]):
        self._docs = docs

    def where(self, *, filter: Any = None, **kwargs: Any) -> MockQuery:
        if filter is not None:
            field = filter.field_path
            op = filter.op_string
            value = filter.value
        else:
            return self

        filtered = []
        for doc_id, data in self._docs:
            val = data.get(field)
            if op == "==" and val == value:
                filtered.append((doc_id, data))
            elif op == ">=" and val is not None and val >= value:
                filtered.append((doc_id, data))
            elif op == "in" and val in value:
                filtered.append((doc_id, data))
        return MockQuery(filtered)

    def order_by(self, field: str, direction: str = "ASCENDING") -> MockQuery:
        reverse = direction == "DESCENDING"
        try:
            sorted_docs = sorted(
                self._docs,
                key=lambda x: (x[1].get(field) is None, x[1].get(field, "")),
                reverse=reverse,
            )
        except TypeError:
            sorted_docs = list(self._docs)
        return MockQuery(sorted_docs)

    def limit(self, count: int) -> MockQuery:
        return MockQuery(self._docs[:count])

    def select(self, fields: list[str]) -> MockQuery:
        projected = []
        for doc_id, data in self._docs:
            projected.append((doc_id, {f: data.get(f) for f in fields}))
        return MockQuery(projected)

    def stream(self) -> list[MockDocumentSnapshot]:
        return [MockDocumentSnapshot(doc_id, data) for doc_id, data in self._docs]


class MockCollectionReference:
    """Simulates a Firestore CollectionReference."""

    def __init__(self, name: str):
        self.name = name
        self._store: dict[str, dict[str, Any]] = {}

    def document(self, doc_id: str | None = None) -> MockDocumentReference:
        if doc_id is None:
            doc_id = uuid.uuid4().hex
        return MockDocumentReference(self, doc_id)

    def add(self, data: dict[str, Any]) -> tuple[Any, MockDocumentReference]:
        ref = self.document()
        ref.set(data)
        return (datetime.now(UTC), ref)

    def where(self, *, filter: Any = None, **kwargs: Any) -> MockQuery:
        docs = list(self._store.items())
        q = MockQuery(docs)
        if filter is not None:
            q = q.where(filter=filter)
        return q

    def order_by(self, field: str, direction: str = "ASCENDING") -> MockQuery:
        docs = list(self._store.items())
        return MockQuery(docs).order_by(field, direction)

    def select(self, fields: list[str]) -> MockQuery:
        docs = list(self._store.items())
        return MockQuery(docs).select(fields)

    def stream(self) -> list[MockDocumentSnapshot]:
        return [MockDocumentSnapshot(k, v) for k, v in self._store.items()]


class MockBatch:
    """Simulates a Firestore WriteBatch."""

    def __init__(self) -> None:
        self._ops: list[tuple[MockDocumentReference, dict[str, Any]]] = []

    def set(self, ref: MockDocumentReference, data: dict[str, Any]) -> None:
        self._ops.append((ref, data))

    def commit(self) -> None:
        for ref, data in self._ops:
            ref.set(data)
        self._ops.clear()


class MockFirestoreClient:
    """In-memory mock of google.cloud.firestore_v1.Client."""

    def __init__(self, **kwargs: Any):
        self._collections: dict[str, MockCollectionReference] = {}

    def collection(self, name: str) -> MockCollectionReference:
        if name not in self._collections:
            self._collections[name] = MockCollectionReference(name)
        return self._collections[name]

    def batch(self) -> MockBatch:
        return MockBatch()

    def clear(self) -> None:
        """Reset all collections (for test cleanup)."""
        self._collections.clear()


# ---------------------------------------------------------------------------
# Inject fake google.cloud.firestore_v1 into sys.modules BEFORE any
# applybot code is imported.  This makes FieldFilter and Client resolvable
# even when the real google-cloud-firestore package is absent.
# ---------------------------------------------------------------------------

_mock_base_query = MagicMock()
_mock_base_query.FieldFilter = MockFieldFilter

_mock_firestore_v1 = MagicMock()
_mock_firestore_v1.Client = MockFirestoreClient
_mock_firestore_v1.base_query = _mock_base_query

# Inject the mocks into sys.modules so "from google.cloud.firestore_v1 import Client"
# and "from google.cloud.firestore_v1.base_query import FieldFilter" both resolve.
sys.modules.setdefault("google", MagicMock())
sys.modules.setdefault("google.cloud", MagicMock())
sys.modules.setdefault("google.cloud.firestore_v1", _mock_firestore_v1)
sys.modules.setdefault("google.cloud.firestore_v1.base_query", _mock_base_query)


# ---------------------------------------------------------------------------
# Autouse fixture — provide a fresh mock Firestore client per test
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def mock_firestore():
    """Provide a fresh mock Firestore client for every test."""
    from unittest.mock import patch

    mock_client = MockFirestoreClient()

    with (
        patch("applybot.models.base._client", mock_client),
        patch("applybot.models.job.get_db", return_value=mock_client),
        patch("applybot.models.application.get_db", return_value=mock_client),
        patch("applybot.models.profile.get_db", return_value=mock_client),
    ):
        yield mock_client
        mock_client.clear()
