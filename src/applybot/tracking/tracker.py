"""Application tracker — state machine for application lifecycle."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from applybot.models.application import (
    Application,
    ApplicationStatus,
    ApplicationStatusUpdate,
    UpdateSource,
)
from applybot.models.base import get_session

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
    application_id: int,
    new_status: ApplicationStatus,
    source: UpdateSource = UpdateSource.MANUAL,
    details: str = "",
) -> Application:
    """Update the status of an application with validation.

    Args:
        application_id: The application to update.
        new_status: Target status.
        source: Who/what triggered this update.
        details: Optional details about the update.

    Returns:
        Updated Application.

    Raises:
        InvalidTransitionError: If the transition is not valid.
        ValueError: If the application doesn't exist.
    """
    with get_session() as session:
        application = session.get(Application, application_id)
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
        session.add(update)

        # Update the application
        application.status = new_status
        if new_status == ApplicationStatus.SUBMITTED:
            application.submitted_at = datetime.now(UTC)

        session.commit()
        session.refresh(application)

        logger.info(
            "Application %d: %s → %s (via %s)",
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
    with get_session() as session:
        query = session.query(Application)
        if status is not None:
            query = query.filter(Application.status == status)
        query = query.order_by(Application.created_at.desc())
        return query.limit(limit).all()


def get_summary() -> dict[str, int]:
    """Get a summary count of applications by status."""
    with get_session() as session:
        counts: dict[str, int] = {}
        for status in ApplicationStatus:
            count = (
                session.query(Application).filter(Application.status == status).count()
            )
            if count > 0:
                counts[status.value] = count
        counts["total"] = session.query(Application).count()
        return counts
