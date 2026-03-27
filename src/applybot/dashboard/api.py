"""FastAPI dashboard backend — REST API for the ApplyBot system."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from applybot.models.application import (
    Application,
    ApplicationStatus,
    UpdateSource,
    get_application,
)
from applybot.models.job import (
    Job,
    JobStatus,
    count_jobs_by_status,
    get_job,
    query_jobs,
    update_job,
)
from applybot.models.profile import (
    UserProfile,
    get_profile,
    save_profile,
)
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
    id: str
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


class ApplicationOut(BaseModel):
    id: str
    job_id: str
    tailored_resume_path: str
    cover_letter: str
    answers: dict[str, Any]
    status: str
    created_at: str
    submitted_at: str | None


class ProfileOut(BaseModel):
    id: str
    name: str
    email: str
    summary: str
    skills: dict[str, Any]
    experiences: list[Any]
    education: list[Any]
    preferences: dict[str, Any]
    resume_path: str


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


# ---------- Health check ----------


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


# ---------- Job endpoints ----------


@app.get("/jobs", response_model=list[JobOut])
def list_jobs(
    status: str | None = None,
    min_score: float | None = None,
    limit: int = Query(default=50, le=500),
) -> list[JobOut]:
    """List discovered jobs, optionally filtered by status and minimum score."""
    job_status = None
    if status:
        try:
            job_status = JobStatus(status)
        except ValueError:
            raise HTTPException(400, f"Invalid status: {status}")
    jobs = query_jobs(status=job_status, min_score=min_score, limit=limit)
    return [_job_to_out(j) for j in jobs]


@app.get("/jobs/{job_id}", response_model=JobOut)
def get_job_endpoint(job_id: str) -> JobOut:
    """Get a specific job by ID."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return _job_to_out(job)


@app.post("/jobs/{job_id}/approve")
def approve_job(job_id: str) -> dict[str, str]:
    """Mark a job for application preparation."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    if job.status != JobStatus.NEW:
        raise HTTPException(400, f"Job is {job.status.value}, not new")
    update_job(job_id, status=JobStatus.APPROVED)
    return {"message": f"Job {job_id} approved for application"}


@app.post("/jobs/{job_id}/skip")
def skip_job(job_id: str) -> dict[str, str]:
    """Skip a job (not interested)."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    update_job(job_id, status=JobStatus.SKIPPED)
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
def get_application_endpoint(app_id: str) -> ApplicationOut:
    """Get a specific application by ID."""
    application = get_application(app_id)
    if application is None:
        raise HTTPException(404, "Application not found")
    return _app_to_out(application)


@app.post("/applications/{app_id}/review")
def review_application(app_id: str, body: StatusUpdate) -> dict[str, str]:
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
def get_profile_endpoint() -> ProfileOut | None:
    """Get the current user profile."""
    profile = get_profile()
    if profile is None:
        return None
    return _profile_to_out(profile)


@app.put("/profile", response_model=ProfileOut)
def update_profile(body: ProfileUpdate) -> ProfileOut:
    """Update the user profile."""
    profile = get_profile()
    if profile is None:
        profile = UserProfile(name=body.name or "", email=body.email or "")
    updates = body.model_dump(exclude_none=True)
    for key, value in updates.items():
        setattr(profile, key, value)
    profile = save_profile(profile)
    return _profile_to_out(profile)


# ---------- Dashboard summary ----------


@app.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary() -> DashboardSummary:
    """Get overall stats for the dashboard."""
    job_counts = count_jobs_by_status()
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
        source=job.source.value if hasattr(job.source, "value") else str(job.source),
        posted_date=job.posted_date.isoformat() if job.posted_date else None,
        discovered_date=job.discovered_date.isoformat() if job.discovered_date else "",
        relevance_score=job.relevance_score,
        relevance_reasoning=job.relevance_reasoning,
        status=job.status.value if hasattr(job.status, "value") else str(job.status),
    )


def _app_to_out(application: Application) -> ApplicationOut:
    return ApplicationOut(
        id=application.id,
        job_id=application.job_id,
        tailored_resume_path=application.tailored_resume_path,
        cover_letter=application.cover_letter,
        answers=application.answers,
        status=(
            application.status.value
            if hasattr(application.status, "value")
            else str(application.status)
        ),
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
