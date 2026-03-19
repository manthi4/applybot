"""FastAPI dashboard backend — REST API for the ApplyBot system."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from applybot.models.application import Application, ApplicationStatus, UpdateSource
from applybot.models.base import get_session
from applybot.models.job import Job, JobStatus
from applybot.models.profile import UserProfile
from applybot.tracking.tracker import (
    InvalidTransitionError,
    get_applications,
    get_summary,
    update_status,
)

app = FastAPI(
    title="ApplyBot Dashboard",
    description="AI-powered job application automation API",
    version="0.1.0",
)


# ---------- Pydantic schemas for API ----------


class JobOut(BaseModel):
    id: int
    title: str
    company: str
    location: str
    description: str
    url: str
    source: str
    posted_date: str | None
    discovered_date: str
    relevance_score: float | None
    relevance_reasoning: str
    status: str

    class Config:
        from_attributes = True


class ApplicationOut(BaseModel):
    id: int
    job_id: int
    tailored_resume_path: str
    cover_letter: str
    answers: dict[str, Any]
    status: str
    created_at: str
    submitted_at: str | None

    class Config:
        from_attributes = True


class ProfileOut(BaseModel):
    id: int
    name: str
    email: str
    summary: str
    skills: dict[str, Any]
    experiences: list[Any]
    education: list[Any]
    preferences: dict[str, Any]
    resume_path: str

    class Config:
        from_attributes = True


class ProfileUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    summary: str | None = None
    skills: dict[str, Any] | None = None
    experiences: list[Any] | None = None
    education: list[Any] | None = None
    preferences: dict[str, Any] | None = None


class StatusUpdate(BaseModel):
    status: str
    details: str = ""


class DashboardSummary(BaseModel):
    jobs: dict[str, int]
    applications: dict[str, int]


# ---------- Job endpoints ----------


@app.get("/jobs", response_model=list[JobOut])
def list_jobs(
    status: str | None = None,
    min_score: float | None = None,
    limit: int = Query(default=50, le=500),
) -> list[JobOut]:
    """List discovered jobs, optionally filtered by status and minimum score."""
    with get_session() as session:
        query = session.query(Job)
        if status:
            try:
                job_status = JobStatus(status)
                query = query.filter(Job.status == job_status)
            except ValueError:
                raise HTTPException(400, f"Invalid status: {status}")
        if min_score is not None:
            query = query.filter(Job.relevance_score >= min_score)
        query = query.order_by(Job.relevance_score.desc().nullslast())
        jobs = query.limit(limit).all()
        return [_job_to_out(j) for j in jobs]


@app.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int) -> JobOut:
    """Get a specific job by ID."""
    with get_session() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(404, "Job not found")
        return _job_to_out(job)


@app.post("/jobs/{job_id}/approve")
def approve_job(job_id: int) -> dict[str, str]:
    """Mark a job for application preparation."""
    with get_session() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(404, "Job not found")
        if job.status != JobStatus.NEW:
            raise HTTPException(400, f"Job is {job.status.value}, not new")
        job.status = JobStatus.APPROVED
        session.commit()
        return {"message": f"Job {job_id} approved for application"}


@app.post("/jobs/{job_id}/skip")
def skip_job(job_id: int) -> dict[str, str]:
    """Skip a job (not interested)."""
    with get_session() as session:
        job = session.get(Job, job_id)
        if job is None:
            raise HTTPException(404, "Job not found")
        job.status = JobStatus.SKIPPED
        session.commit()
        return {"message": f"Job {job_id} skipped"}


# ---------- Application endpoints ----------


@app.get("/applications", response_model=list[ApplicationOut])
def list_applications(
    status: str | None = None,
    limit: int = Query(default=50, le=500),
) -> list[ApplicationOut]:
    """List applications, optionally filtered by status."""
    app_status = None
    if status:
        try:
            app_status = ApplicationStatus(status)
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")
    apps = get_applications(status=app_status, limit=limit)
    return [_app_to_out(a) for a in apps]


@app.get("/applications/{app_id}", response_model=ApplicationOut)
def get_application(app_id: int) -> ApplicationOut:
    """Get a specific application by ID."""
    with get_session() as session:
        application = session.get(Application, app_id)
        if application is None:
            raise HTTPException(404, "Application not found")
        return _app_to_out(application)


@app.post("/applications/{app_id}/review")
def review_application(app_id: int, body: StatusUpdate) -> dict[str, str]:
    """Update application status (approve, reject, etc.)."""
    try:
        new_status = ApplicationStatus(body.status)
    except ValueError:
        raise HTTPException(400, f"Invalid status: {body.status}")

    try:
        update_status(app_id, new_status, UpdateSource.MANUAL, body.details)
        return {"message": f"Application {app_id} updated to {new_status.value}"}
    except ValueError as e:
        raise HTTPException(404, str(e))
    except InvalidTransitionError as e:
        raise HTTPException(400, str(e))


# ---------- Profile endpoints ----------


@app.get("/profile", response_model=ProfileOut | None)
def get_profile() -> ProfileOut | None:
    """Get the current user profile."""
    with get_session() as session:
        profile = session.query(UserProfile).first()
        if profile is None:
            return None
        return _profile_to_out(profile)


@app.put("/profile", response_model=ProfileOut)
def update_profile(body: ProfileUpdate) -> ProfileOut:
    """Update the user profile."""
    with get_session() as session:
        profile = session.query(UserProfile).first()
        if profile is None:
            profile = UserProfile(name=body.name or "", email=body.email or "")
            session.add(profile)
        updates = body.model_dump(exclude_none=True)
        for key, value in updates.items():
            setattr(profile, key, value)
        session.commit()
        session.refresh(profile)
        return _profile_to_out(profile)


# ---------- Dashboard summary ----------


@app.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary() -> DashboardSummary:
    """Get overall stats for the dashboard."""
    with get_session() as session:
        job_counts: dict[str, int] = {}
        for status in JobStatus:
            count = session.query(Job).filter(Job.status == status).count()
            if count > 0:
                job_counts[status.value] = count
        job_counts["total"] = session.query(Job).count()

    app_counts = get_summary()

    return DashboardSummary(jobs=job_counts, applications=app_counts)


# ---------- Helpers ----------


def _job_to_out(job: Job) -> JobOut:
    return JobOut(
        id=job.id,
        title=job.title,
        company=job.company,
        location=job.location,
        description=job.description,
        url=job.url,
        source=job.source.value,
        posted_date=job.posted_date.isoformat() if job.posted_date else None,
        discovered_date=job.discovered_date.isoformat() if job.discovered_date else "",
        relevance_score=job.relevance_score,
        relevance_reasoning=job.relevance_reasoning,
        status=job.status.value,
    )


def _app_to_out(application: Application) -> ApplicationOut:
    return ApplicationOut(
        id=application.id,
        job_id=application.job_id,
        tailored_resume_path=application.tailored_resume_path,
        cover_letter=application.cover_letter,
        answers=application.answers,
        status=application.status.value,
        created_at=application.created_at.isoformat() if application.created_at else "",
        submitted_at=(
            application.submitted_at.isoformat() if application.submitted_at else None
        ),
    )


def _profile_to_out(profile: UserProfile) -> ProfileOut:
    return ProfileOut(
        id=profile.id,
        name=profile.name,
        email=profile.email,
        summary=profile.summary,
        skills=profile.skills or {},
        experiences=profile.experiences or [],
        education=profile.education or [],
        preferences=profile.preferences or {},
        resume_path=profile.resume_path,
    )
