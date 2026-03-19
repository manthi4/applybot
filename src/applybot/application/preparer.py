"""Application preparer — orchestrates resume tailoring and question answering."""

from __future__ import annotations

import logging

from applybot.application.question_answerer import (
    ProfileGap,
    answer_questions,
    generate_cover_letter,
)
from applybot.application.resume_tailor import tailor_resume
from applybot.models.application import Application, ApplicationStatus
from applybot.models.base import get_session
from applybot.models.job import Job, JobStatus
from applybot.profile.manager import ProfileManager

logger = logging.getLogger(__name__)


def prepare_application(
    job: Job,
    custom_questions: list[str] | None = None,
) -> tuple[Application, list[ProfileGap]]:
    """Prepare a full application for a job.

    Steps:
    1. Tailor resume for the job
    2. Answer standard + custom questions
    3. Generate cover letter
    4. Save Application record with status READY_FOR_REVIEW

    Args:
        job: The job to apply to (must have status APPROVED).
        custom_questions: Additional application-specific questions.

    Returns:
        Tuple of (Application record, list of profile gaps).
    """
    pm = ProfileManager()
    profile = pm.get_profile()
    if profile is None:
        raise ValueError("No user profile exists. Set up your profile first.")

    all_gaps: list[ProfileGap] = []

    # 1. Tailor resume
    resume_path = ""
    try:
        tailored_path = tailor_resume(job, profile)
        resume_path = str(tailored_path)
    except FileNotFoundError:
        logger.warning("No base resume found — skipping resume tailoring")
    except Exception:
        logger.exception("Resume tailoring failed for job %d", job.id)

    # 2. Answer questions
    answers, gaps = answer_questions(job, profile, custom_questions)
    all_gaps.extend(gaps)

    # 3. Generate cover letter
    cover_letter = generate_cover_letter(job, profile)

    # 4. Save to database
    with get_session() as session:
        application = Application(
            job_id=job.id,
            tailored_resume_path=resume_path,
            cover_letter=cover_letter,
            answers=answers,
            status=ApplicationStatus.READY_FOR_REVIEW,
        )
        session.add(application)
        session.commit()
        session.refresh(application)

        logger.info(
            "Application prepared: id=%d for job %d (%s at %s), %d gaps",
            application.id,
            job.id,
            job.title,
            job.company,
            len(all_gaps),
        )
        return application, all_gaps


def prepare_all_approved() -> list[tuple[Application, list[ProfileGap]]]:
    """Prepare applications for all jobs with APPROVED status.

    Returns:
        List of (Application, gaps) tuples.
    """
    results: list[tuple[Application, list[ProfileGap]]] = []

    with get_session() as session:
        approved_jobs = (
            session.query(Job).filter(Job.status == JobStatus.APPROVED).all()
        )

    logger.info("Found %d approved jobs to prepare", len(approved_jobs))

    for job in approved_jobs:
        try:
            app, gaps = prepare_application(job)
            results.append((app, gaps))

            # Update job status
            with get_session() as session:
                session.query(Job).filter(Job.id == job.id).update(
                    {Job.status: JobStatus.REVIEWING}
                )
                session.commit()

        except Exception:
            logger.exception("Failed to prepare application for job %d", job.id)

    logger.info("Prepared %d applications", len(results))
    return results
