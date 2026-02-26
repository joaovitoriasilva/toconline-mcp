"""CLI entry point for ``toconline-mcp``.

Subcommands
-----------
``toconline-mcp``           – (default) run the MCP server over stdio.
``toconline-mcp auth``      – one-time PKCE browser login; stores refresh token in keychain.
``toconline-mcp auth --status``  – check if a token is stored.
``toconline-mcp auth --logout``  – delete the stored token.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import webbrowser
from urllib.parse import parse_qs, urlparse

import httpx

from toconline_mcp.auth import exchange_code_for_tokens, make_auth_url
from toconline_mcp.keychain import (
    delete_refresh_token,
    has_refresh_token,
    store_refresh_token,
)
from toconline_mcp.settings import Settings, get_settings


# ── Helpers ─────────────────────────────────────────────────────────────────


def _extract_code(user_input: str) -> str | None:
    """Extract the authorization code from user input.

    Accepts either:
    - A full callback URL containing ``?code=…``
    - The raw authorization code string
    """
    user_input = user_input.strip()
    if not user_input:
        return None

    # If it looks like a URL, parse the 'code' query parameter.
    if user_input.startswith("http://") or user_input.startswith("https://"):
        parsed = urlparse(user_input)
        qs = parse_qs(parsed.query)
        return qs.get("code", [None])[0]

    # Otherwise treat the whole input as the code.
    return user_input


# ── Subcommands ─────────────────────────────────────────────────────────────


def _run_auth(args: argparse.Namespace) -> None:
    """Handle ``toconline-mcp auth``."""
    if args.status:
        _auth_status()
        return
    if args.logout:
        _auth_logout()
        return
    _auth_login()


def _auth_status() -> None:
    """Show whether a refresh token is stored in the keychain."""
    if has_refresh_token():
        print("✓ A refresh token is stored in the system keychain.")
    else:
        settings = get_settings()
        if settings.refresh_token:
            print(
                "⚠ No token in keychain, but TOCONLINE_REFRESH_TOKEN is set in .env "
                "(less secure)."
            )
        else:
            print("✗ No refresh token found. Run 'toconline-mcp auth' to authenticate.")


def _auth_logout() -> None:
    """Delete the stored refresh token."""
    if delete_refresh_token():
        print("✓ Refresh token removed from system keychain.")
    else:
        print("⚠ Could not delete — keychain backend may not be available.")


def _auth_login() -> None:
    """Perform the full PKCE browser login flow.

    Opens the browser for TOC Online login using the registered redirect URI.
    After the user authorizes, they paste the authorization code (or the full
    callback URL) back into the terminal.
    """
    settings = get_settings()

    if not settings.client_id or not settings.client_secret:
        print(
            "✗ TOCONLINE_CLIENT_ID and TOCONLINE_CLIENT_SECRET must be set in .env.",
            file=sys.stderr,
        )
        sys.exit(1)

    auth_url, code_verifier, expected_state = make_auth_url(settings)

    print("Opening browser for TOC Online login\u2026")
    print(f"  {auth_url}\n")

    # Try to open the browser; if it fails the user can paste the URL manually.
    webbrowser.open(auth_url)

    print("After you authorize, you will be redirected to the callback URL.")
    print(
        "Copy the full URL from your browser (or just the code) and paste it below.\n"
    )

    try:
        user_input = input("Paste the callback URL or authorization code: ")
    except (KeyboardInterrupt, EOFError):
        print("\n\u2717 Cancelled.", file=sys.stderr)
        sys.exit(1)

    # Verify the OAuth2 state parameter to prevent CSRF attacks.
    user_input_stripped = user_input.strip()
    if user_input_stripped.startswith(("http://", "https://")):
        _qs = parse_qs(urlparse(user_input_stripped).query)
        returned_state = _qs.get("state", [None])[0]
        if returned_state != expected_state:
            print(
                "\u2717 OAuth state mismatch \u2014 possible CSRF attack. Aborting.",
                file=sys.stderr,
            )
            sys.exit(1)

    code = _extract_code(user_input)

    if not code:
        print(
            "✗ Could not extract an authorization code from your input.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("\n✓ Authorization code received. Exchanging for tokens…")

    # Exchange the code for tokens.
    tokens = asyncio.run(_exchange(code, code_verifier, settings))

    refresh_token = tokens.get("refresh_token", "")
    access_token = tokens.get("access_token", "")
    expires_in = tokens.get("expires_in", "?")

    if not refresh_token:
        print("✗ Token response did not contain a refresh_token.", file=sys.stderr)
        sys.exit(1)

    # Store in keychain.
    if store_refresh_token(refresh_token):
        print("✓ Refresh token stored in system keychain.")
    else:
        print(
            "⚠ Could not store in keychain.\n"
            "  Copy the refresh token from the response and set it in your\n"
            "  .env file as TOCONLINE_REFRESH_TOKEN=<paste-token-here>"
        )

    print(f"\n✓ Access token received (expires in {expires_in}s).")
    print("You're all set! The MCP server will renew tokens automatically.")


async def _exchange(
    code: str, code_verifier: str, settings: Settings
) -> dict[str, str]:
    """Async wrapper around exchange_code_for_tokens for use in sync CLI."""
    async with httpx.AsyncClient() as client:
        return await exchange_code_for_tokens(code, code_verifier, settings, client)


def _run_serve(_args: argparse.Namespace) -> None:
    """Handle the default (no subcommand) action: run the MCP server."""
    from toconline_mcp.server import main as server_main

    server_main()


# ── Argument parser ─────────────────────────────────────────────────────────


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="toconline-mcp",
        description="TOC Online MCP server",
    )
    subparsers = parser.add_subparsers(dest="command")

    # ``toconline-mcp auth``
    auth_parser = subparsers.add_parser(
        "auth",
        help="Authenticate with TOC Online (one-time browser login).",
    )
    auth_group = auth_parser.add_mutually_exclusive_group()
    auth_group.add_argument(
        "--status",
        action="store_true",
        help="Check if credentials are stored in the keychain.",
    )
    auth_group.add_argument(
        "--logout",
        action="store_true",
        help="Remove stored credentials from the keychain.",
    )

    return parser


def main() -> None:
    """CLI entry point — ``toconline-mcp``."""
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "auth":
        _run_auth(args)
    else:
        # Default: run the MCP server.
        _run_serve(args)
