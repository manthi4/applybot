"""FastHTML dashboard frontend for ApplyBot."""

from __future__ import annotations

import hashlib

import pyotp
from fasthtml.common import (
    H2,
    Button,
    Card,
    Container,
    Form,
    Input,
    Label,
    Main,
    P,
    RedirectResponse,
    fast_app,
)
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.middleware.sessions import SessionMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response
from starlette.responses import RedirectResponse as StarletteRedirect

from applybot.config import settings
from applybot.dashboard.components import alert
from applybot.dashboard.pages import apps, jobs, overview, profile
from applybot.dashboard.theme import theme_headers

app, rt = fast_app(
    title="ApplyBot Dashboard",
    pico=True,
    htmlkw={"data-theme": "dark"},
    hdrs=theme_headers,
)

# ---------- Auth setup ----------

# Derive session signing key from TOTP secret — one secret to manage.
# Falls back to an insecure placeholder when auth is disabled (dev mode).
_session_secret = (
    hashlib.sha256(settings.dashboard_totp_secret.encode()).hexdigest()
    if settings.dashboard_totp_secret
    else "dev-insecure-session-key-do-not-use-in-production"
)


class _AuthMiddleware(BaseHTTPMiddleware):
    """Redirect unauthenticated requests to /login. /healthz and /login are open."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.url.path in ("/healthz", "/login"):
            return await call_next(request)
        if not request.session.get("authenticated"):
            return StarletteRedirect("/login", status_code=303)
        return await call_next(request)


# Middleware is applied in reverse add order: last added = outermost.
# SessionMiddleware (outermost) decodes the cookie first, then _AuthMiddleware
# can safely read request.session.
app.add_middleware(_AuthMiddleware)
app.add_middleware(
    SessionMiddleware,
    secret_key=_session_secret,
    https_only=bool(settings.dashboard_totp_secret),
    max_age=86400,  # 24-hour session
)


# ---------- Login / logout routes ----------


@rt("/login")
def get(error: str = "") -> tuple[object, ...]:
    """Login page — enter 6-digit TOTP code."""
    return (
        Main(
            Container(
                Card(
                    H2("ApplyBot"),
                    P("Enter your 6-digit authenticator code."),
                    alert("Invalid code — try again.", "error") if error else "",
                    Form(
                        Label(
                            "Code",
                            Input(
                                name="code",
                                type="text",
                                inputmode="numeric",
                                pattern="[0-9]{6}",
                                maxlength="6",
                                autocomplete="off",
                                autofocus=True,
                                placeholder="000000",
                            ),
                        ),
                        Button("Sign in", type="submit"),
                        method="post",
                        action="/login",
                    ),
                    style="max-width:360px;margin:80px auto",
                )
            ),
            cls="container",
        ),
    )


@rt("/login")
def post(code: str, request: Request) -> RedirectResponse:
    """Validate TOTP code and set session on success."""
    totp_secret = settings.dashboard_totp_secret
    if not totp_secret:
        # Dev mode: auth disabled, accept anything
        request.session["authenticated"] = True
        return RedirectResponse("/", status_code=303)
    totp = pyotp.TOTP(totp_secret)
    if totp.verify(code, valid_window=1):
        request.session["authenticated"] = True
        return RedirectResponse("/", status_code=303)
    return RedirectResponse("/login?error=1", status_code=303)


@rt("/logout")
def logout_post(request: Request) -> RedirectResponse:
    """Clear session and redirect to login."""
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


# ---------- Dashboard pages ----------

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
