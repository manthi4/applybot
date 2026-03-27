"""Application tracker — state machine for application lifecycle."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from applybot.models.application import (
    Application,
    ApplicationStatus,
    ApplicationStatusUpdate,
    UpdateSource,
    add_status_update,
    count_applications_by_status,
    get_application,
    query_applications,
    update_application,
)

logger = logging.getLogger(__name__)

# Valid state transitions
VALID_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.DRAFT: {
        ApplicationStatus.READY_FOR_REVIEW,
        ApplicationStatus.WITHDRAWN,
    },
    ApplicationStatus.READY_FOR_REVIEW: {
        ApplicationStatus.APPROVED,
        ApplicationStatus.DRAFT,  # back to draft for re-work
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
    source: UpdateSource = UpdateSource.MANUAL,
    details: str = "",
) -> Application:
    """Update the status of an application with validation."""
    application = get_application(application_id)
    if application is None:
        raise ValueError(f"Application {application_id} not found")

    current = application.status
    valid_next = VALID_TRANSITIONS.get(current, set())

    if new_status not in valid_next:
        raise InvalidTransitionError(
            f"Cannot transition from {current.value} to {new_status.value}. "
            f"Valid transitions: {[s.value for s in valid_next]}"
        )

    # Create status update record
    update = ApplicationStatusUpdate(
        application_id=application_id,
        status=new_status,
        source=source,
        details=details,
        timestamp=datetime.now(UTC),
    )
    add_status_update(update)

    # Update the application
    fields: dict[str, Any] = {"status": new_status}
    if new_status == ApplicationStatus.SUBMITTED:
        fields["submitted_at"] = datetime.now(UTC)
    update_application(application_id, **fields)

    # Re-read and return
    application = get_application(application_id)
    assert application is not None

    logger.info(
        "Application %s: %s → %s (via %s)",
        application_id,
        current.value,
        new_status.value,
        source.value,
    )
    return application


def get_applications(
    status: ApplicationStatus | None = None,
    limit: int = 100,
) -> list[Application]:
    """Get applications, optionally filtered by status."""
    return query_applications(status=status, limit=limit)


def get_summary() -> dict[str, int]:
    """Get a summary count of applications by status."""
    return count_applications_by_status()
