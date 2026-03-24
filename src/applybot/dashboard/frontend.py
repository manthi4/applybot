"""FastHTML dashboard frontend for ApplyBot."""

from __future__ import annotations

from fasthtml.common import fast_app
from starlette.responses import PlainTextResponse

from applybot.dashboard.pages import apps, jobs, overview, profile
from applybot.dashboard.theme import theme_headers

app, rt = fast_app(
    title="ApplyBot Dashboard",
    pico=True,
    htmlkw={"data-theme": "dark"},
    hdrs=theme_headers,
)

# Register all page routes
overview.register(rt)
jobs.register(rt)
apps.register(rt)
profile.register(rt)


@rt("/healthz")
def healthz() -> PlainTextResponse:
    return PlainTextResponse("ok")


def main(host: str = "127.0.0.1", port: int = 8000, reload: bool = False) -> None:
    """Start the FastHTML dashboard server."""
    import uvicorn

    print(f"Starting ApplyBot dashboard at http://{host}:{port}")
    uvicorn.run(
        "applybot.dashboard.frontend:app",
        host=host,
        port=port,
        reload=reload,
    )


if __name__ == "__main__":
    main()
