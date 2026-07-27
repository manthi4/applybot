"""Application tracker — state machine for application lifecycle."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from applybot.models.application import Application, ApplicationStatus

logger = logging.getLogger(__name__)

# Valid state transitions
VALID_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.READY_FOR_REVIEW: {
        ApplicationStatus.APPROVED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.APPROVED: {
        ApplicationStatus.SUBMITTED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.SUBMITTED: {
        ApplicationStatus.RECEIVED,
        ApplicationStatus.INTERVIEW,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.RECEIVED: {
        ApplicationStatus.INTERVIEW,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.INTERVIEW: {
        ApplicationStatus.OFFER,
        ApplicationStatus.REJECTED,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.OFFER: {
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.REJECTED: set(),  # terminal state
    ApplicationStatus.WITHDRAWN: set(),  # terminal state
}


class InvalidTransitionError(Exception):
    pass


def update_status(
    application_id: str,
    new_status: ApplicationStatus,
) -> Application:
    """Update the status of an application with validation."""
    application = Application.get(application_id)
    if application is None:
        raise ValueError(f"Application {application_id} not found")

    current = application.status
    valid_next = VALID_TRANSITIONS.get(current, set())

    if new_status not in valid_next:
        raise InvalidTransitionError(
            f"Cannot transition from {current.value} to {new_status.value}. "
            f"Valid transitions: {[s.value for s in valid_next]}"
        )

    # Update the application
    fields: dict[str, Any] = {"status": new_status}
    if new_status == ApplicationStatus.SUBMITTED:
        fields["submitted_at"] = datetime.now(UTC)
    Application.update(application_id, **fields)

    # Re-read and return
    application = Application.get(application_id)
    assert application is not None

    logger.info(
        "Application %s: %s → %s",
        application_id,
        current.value,
        new_status.value,
    )
    return application


def get_applications(
    status: ApplicationStatus | None = None,
    limit: int = 100,
) -> list[Application]:
    """Get applications, optionally filtered by status."""
    return Application.query(status=status, limit=limit)


def get_summary() -> dict[str, int]:
    """Get a summary count of applications by status."""
    return Application.count_by_status()
