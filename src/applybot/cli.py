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
    """Verify Firestore connection."""
    from applybot.models.base import init_db as _init_db

    _init_db()
    click.echo("Firestore connection verified successfully.")


@cli.command()
@click.option("--host", default="127.0.0.1", help="Host to bind to")
@click.option("--port", default=None, type=int, help="Port to bind to")
@click.option("--reload", is_flag=True, help="Enable auto-reload for development")
def serve(host: str, port: int | None, reload: bool) -> None:
    """Start the FastHTML dashboard server."""
    from applybot.config import settings
    from applybot.dashboard.frontend import main as run_dashboard

    run_dashboard(host=host, port=port or settings.port, reload=reload)


@cli.command("bootstrap-profile")
@click.argument("resume_path", type=click.Path(exists=True))
@click.option("--name", default=None, help="Override name from resume")
@click.option("--email", default=None, help="Set email address")
def bootstrap_profile(resume_path: str, name: str | None, email: str | None) -> None:
    """Import a .docx resume and create/update the user profile."""
    from applybot.profile.manager import ProfileManager
    from applybot.profile.resume import parse_resume

    resume_file = Path(resume_path).resolve()

    if resume_file.suffix.lower() != ".docx":
        raise click.BadParameter(
            "Resume file must be a .docx file.", param_hint="resume_path"
        )

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


@cli.command("run-discovery")
@click.option("--location", default="", help="Location filter for job search")
@click.option("--max-results", default=None, type=int, help="Max jobs to return")
def run_discovery_cmd(location: str, max_results: int | None) -> None:
    """Run the job discovery pipeline."""
    import asyncio

    from applybot.discovery.orchestrator import run_discovery

    result = asyncio.run(run_discovery(location=location, max_results=max_results))
    click.echo("Discovery complete:")
    click.echo(f"  Scraped:    {result.total_scraped}")
    click.echo(f"  Unique:     {result.after_dedup}")
    click.echo(f"  Relevant:   {result.above_threshold}")
    click.echo(f"  New saved:  {result.new_jobs_saved}")
    if result.top_matches:
        click.echo("\nTop matches:")
        for match in result.top_matches[:5]:
            click.echo(f"  [{match['score']}] {match['title']} @ {match['company']}")


@cli.command("setup-auth")
@click.option(
    "--issuer", default="ApplyBot", help="Name shown in your authenticator app"
)
def setup_auth(issuer: str) -> None:
    """Print the TOTP secret and QR code URI for your authenticator app.

    If DASHBOARD_TOTP_SECRET is not set, a new random secret is generated and
    printed — copy it into your .env file and Secret Manager before using.
    """
    import pyotp

    from applybot.config import settings

    totp_secret = settings.dashboard_totp_secret
    if not totp_secret:
        totp_secret = pyotp.random_base32()
        click.echo("No DASHBOARD_TOTP_SECRET found. Generated a new one:\n")
        click.echo(f"  DASHBOARD_TOTP_SECRET={totp_secret}\n")
        click.echo(
            "  Add this to your .env file (local) and GCP Secret Manager (production).\n"
        )

    totp = pyotp.TOTP(totp_secret)
    uri = totp.provisioning_uri(name="admin", issuer_name=issuer)

    click.echo("Scan this URI with Google Authenticator, Authy, or any TOTP app:")
    click.echo(f"\n  {uri}\n")
    click.echo("Or open this URL in a browser to display a scannable QR code:")
    click.echo(
        f"  https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={uri}\n"
    )
    click.echo("Current code (valid for ~30 s):")
    click.echo(f"  {totp.now()}")
