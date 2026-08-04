"""ApplyBot command-line interface."""

from __future__ import annotations

import argparse


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="applybot", description="ApplyBot CLI.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_serve = sub.add_parser("serve", help="Start the dashboard web server.")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=None)
    p_serve.add_argument("--reload", action="store_true")

    sub.add_parser("setup-auth", help="Generate a TOTP secret for dashboard auth.")

    args = parser.parse_args(argv)

    if args.command == "serve":
        from applybot.config import settings
        from applybot.dashboard.frontend import main as serve_main

        port = args.port if args.port is not None else settings.port
        serve_main(host=args.host, port=port, reload=args.reload)
    elif args.command == "setup-auth":
        _setup_auth()


def _setup_auth() -> None:
    import pyotp

    secret = pyotp.random_base32()
    uri = pyotp.TOTP(secret).provisioning_uri(name="ApplyBot", issuer_name="ApplyBot")
    print("Add this to your .env (local) or GCP Secret Manager (production):")
    print(f"  DASHBOARD_TOTP_SECRET={secret}")
    print()
    print("Enter this secret manually in your authenticator app")
    print("(Google Authenticator, Authy, 1Password, etc.):")
    print(f"  secret: {secret}")
    print()
    print(f"otpauth URI: {uri}")


if __name__ == "__main__":
    main()
