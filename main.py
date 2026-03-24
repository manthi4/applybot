"""Google Cloud Function entry point for the discovery pipeline."""

from __future__ import annotations

import asyncio
import json
import logging

import functions_framework
from flask import Request, Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@functions_framework.http
def handle_discovery(request: Request) -> Response:
    """HTTP Cloud Function that runs the job discovery pipeline.

    Triggered by Cloud Scheduler on a cron schedule.
    """
    from applybot.discovery.orchestrator import run_discovery

    logger.info("Starting discovery run")

    try:
        result = asyncio.run(run_discovery())
    except Exception:
        logger.exception("Discovery run failed")
        return Response(
            json.dumps({"error": "Discovery run failed"}),
            status=500,
            mimetype="application/json",
        )

    body = {
        "total_scraped": result.total_scraped,
        "after_dedup": result.after_dedup,
        "above_threshold": result.above_threshold,
        "new_jobs_saved": result.new_jobs_saved,
        "top_matches": result.top_matches,
    }

    logger.info("Discovery complete: %d new jobs saved", result.new_jobs_saved)

    return Response(
        json.dumps(body, default=str),
        status=200,
        mimetype="application/json",
    )
