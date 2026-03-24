"""ApplyBot command-line interface."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import click


@click.group()
def cli() -> None:
    """ApplyBot — AI-powered job application automation."""
    logging.basicConfig(level=logging.INFO)


@cli.command()
def init_db() -> None:
    """Initialize the database (run migrations)."""
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    click.echo("Database initialized successfully.")


@cli.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to")
@click.option("--port", default=None, type=int, help="Port to bind to")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
def serve(host: str, port: int | None, reload: bool) -> None:
    """Start the FastHTML dashboard server."""
    from applybot.config import settings
    from applybot.dashboard.frontend import main as run_dashboard

    run_dashboard(host=host, port=port or settings.port, reload=reload)


@cli.command("serve-api")
@click.option("--host", default="127.0.0.1", help="Host to bind to")
@click.option("--port", default=None, type=int, help="Port to bind to")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
def serve_api(host: str, port: int | None, reload: bool) -> None:
    """Start the FastAPI REST API server."""
    import uvicorn

    from applybot.config import settings

    uvicorn.run(
        "applybot.dashboard.api:app",
        host=host,
        port=port or settings.port,
        reload=reload,
    )


@cli.command("bootstrap-profile")
@click.argument("resume_path", type=click.Path(exists=True))
@click.option("--name", default=None, help="Override name from resume")
@click.option("--email", default=None, help="Set email address")
def bootstrap_profile(resume_path: str, name: str | None, email: str | None) -> None:
    """Import a .docx resume and create/update the user profile."""
    from applybot.models.base import init_db
    from applybot.profile.manager import ProfileManager
    from applybot.profile.resume import parse_resume

    resume_file = Path(resume_path).resolve()

    if resume_file.suffix.lower() != ".docx":
        raise click.BadParameter(
            "Resume file must be a .docx file.", param_hint="resume_path"
        )

    init_db()

    resume_data = parse_resume(resume_file)

    resolved_name = name if name is not None else resume_data.name
    resolved_email = email if email is not None else ""

    # Find sections by searching headings case-insensitively for keywords
    skills_section = next(
        (s for s in resume_data.sections if "skill" in s.heading.lower()), None
    )
    experience_section = next(
        (s for s in resume_data.sections if "experience" in s.heading.lower()), None
    )
    education_section = next(
        (s for s in resume_data.sections if "education" in s.heading.lower()), None
    )

    skills: dict[str, Any] = {"items": skills_section.items} if skills_section else {}
    experiences: list[dict[str, str]] = (
        [{"text": item} for item in experience_section.items]
        if experience_section
        else []
    )
    education: list[dict[str, str]] = (
        [{"text": item} for item in education_section.items]
        if education_section
        else []
    )

    pm = ProfileManager()
    pm.get_or_create_profile(name=resolved_name, email=resolved_email)
    pm.update_profile(
        name=resolved_name,
        email=resolved_email,
        summary=resume_data.summary,
        skills=skills,
        experiences=experiences,
        education=education,
        resume_path=str(resume_file),
    )

    click.echo("Profile bootstrapped successfully.")
    click.echo(f"  Name:        {resolved_name}")
    click.echo(f"  Email:       {resolved_email}")
    click.echo(f"  Skills:      {len(skills.get('items', []))} items")
    click.echo(f"  Experiences: {len(experiences)} items")
    click.echo(f"  Education:   {len(education)} items")
    click.echo(f"  Resume:      {resume_file}")
