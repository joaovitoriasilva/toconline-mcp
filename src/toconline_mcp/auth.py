"""OAuth2 Bearer token management for the TOC Online API.

TOC Online uses the authorization_code OAuth2 flow with PKCE (S256).

Key facts from the Postman collection:
  - client_authentication: "body" — credentials go in the request body, NOT as Basic auth.
  - challengeAlgorithm: "S256" — PKCE is required.
  - base_url_oauth: https://app10.toconline.pt/oauth → token URL ends in /token, auth in /auth.
  - base_url (API): https://api10.toconline.pt

Flow:
  1. generate_pkce_pair() → code_verifier + code_challenge.
  2. make_auth_url() → browser URL with code_challenge; user logs in, gets authorization_code.
  3. exchange_code_for_tokens() → POST /token with code + code_verifier + client creds in body.
  4. Store refresh_token; TokenStore.refresh() renews access_token silently from then on.
"""

from __future__ import annotations

import base64
import hashlib
import os
import time
from dataclasses import dataclass, field
from urllib.parse import urlencode

import httpx

from toconline_mcp.settings import Settings


def _generate_pkce_pair() -> tuple[str, str]:
    """Generate a PKCE (code_verifier, code_challenge) pair using S256.

    Returns:
        (code_verifier, code_challenge) — both base64url-encoded, no padding.
    """
    verifier_bytes = os.urandom(32)
    code_verifier = base64.urlsafe_b64encode(verifier_bytes).rstrip(b"=").decode()
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return code_verifier, code_challenge


def _generate_state() -> str:
    """Generate a random OAuth2 state parameter for CSRF protection.

    Returns a base64url-encoded string (no padding) from 16 random bytes.
    """
    return base64.urlsafe_b64encode(os.urandom(16)).rstrip(b"=").decode()


def make_auth_url(settings: Settings) -> tuple[str, str, str]:
    """Return (auth_url, code_verifier, state) for the one-time PKCE authorization flow.

    The caller must persist the code_verifier and pass it to
    exchange_code_for_tokens() after the user completes the browser login.
    The caller should verify the returned ``state`` matches the callback.
    """
    auth_endpoint = settings.oauth_token_url.replace("/token", "/auth")
    redirect_uri = settings.redirect_uri or "https://oauth.pstmn.io/v1/callback"
    code_verifier, code_challenge = _generate_pkce_pair()
    state = _generate_state()
    params = urlencode(
        {
            "client_id": settings.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "commercial",
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
            "state": state,
        }
    )
    return f"{auth_endpoint}?{params}", code_verifier, state


async def exchange_code_for_tokens(
    code: str,
    code_verifier: str,
    settings: Settings,
    client: httpx.AsyncClient,
) -> dict[str, str]:
    """Exchange an authorization_code for an access_token and refresh_token.

    Credentials and the PKCE code_verifier are sent in the request body
    (client_authentication=body), matching the Postman collection configuration.

    Returns the full token payload dict from the API.
    Raises httpx.HTTPStatusError on failure.
    """
    redirect_uri = settings.redirect_uri or "https://oauth.pstmn.io/v1/callback"
    response = await client.post(
        settings.oauth_token_url,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": settings.client_id,
            "client_secret": settings.client_secret,
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
            "scope": "commercial",
        },
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        },
    )
    response.raise_for_status()
    return response.json()  # type: ignore[return-value]


@dataclass
class TokenStore:
    """Holds and refreshes an OAuth2 Bearer token.

    Supports two modes:
    - Static token: load_static() — token never expires (use TOCONLINE_ACCESS_TOKEN).
    - Refresh flow: load_refresh_token() — auto-renews via TOCONLINE_REFRESH_TOKEN.
    """

    _access_token: str = field(default="", repr=False)
    _refresh_token: str = field(default="", repr=False)
    _expires_at: float = field(default=0.0)

    def load_static(self, token: str) -> None:
        """Use a static, non-expiring access token from configuration."""
        self._access_token = token
        self._expires_at = float("inf")

    def load_refresh_token(self, refresh_token: str) -> None:
        """Store a refresh token so the access token can be renewed automatically."""
        self._refresh_token = refresh_token

    @property
    def is_valid(self) -> bool:
        """Return True if the stored token is still valid (with a 60-second buffer)."""
        return bool(self._access_token) and time.time() < self._expires_at - 60

    @property
    def bearer(self) -> str:
        """Return the Authorization header value."""
        return f"Bearer {self._access_token}"

    async def refresh(self, settings: Settings, client: httpx.AsyncClient) -> None:
        """Fetch a new access token using the refresh_token grant.

        Credentials are sent in the request body (client_authentication=body),
        matching the Postman collection configuration.
        The new refresh_token returned by the API is stored for the next renewal.
        """
        if not settings.client_id or not settings.client_secret:
            raise RuntimeError(
                "TOCONLINE_ACCESS_TOKEN is missing or expired, and "
                "TOCONLINE_CLIENT_ID / TOCONLINE_CLIENT_SECRET are not configured."
            )

        refresh_token = self._refresh_token or settings.refresh_token
        if not refresh_token:
            raise RuntimeError(
                "No valid access token and no refresh_token available.\n"
                "Run 'uv run toconline-mcp auth' in a terminal to authenticate via browser,\n"
                "or set TOCONLINE_REFRESH_TOKEN in your .env file."
            )

        response = await client.post(
            settings.oauth_token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": settings.client_id,
                "client_secret": settings.client_secret,
                "scope": "commercial",
            },
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )
        response.raise_for_status()
        payload = response.json()
        self._access_token = payload["access_token"]
        self._expires_at = time.time() + int(payload.get("expires_in", 7890000))
        # Store the new refresh token if one is returned, so the chain continues.
        if new_refresh := payload.get("refresh_token"):
            self._refresh_token = new_refresh
            # Persist to keychain so the token survives process restarts.
            from toconline_mcp.keychain import store_refresh_token

            store_refresh_token(new_refresh)
