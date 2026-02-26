"""Async HTTP client wrapper for the TOC Online API.

Handles:
  - Base URL injection
  - Automatic Authorization header via TokenStore
  - JSON:API Content-Type
  - Error normalization into Python exceptions
  - 401 token-expiry retry (refresh + single retry)
  - Status-specific error messages for 403, 404, 422
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from toconline_mcp.auth import TokenStore
from toconline_mcp.settings import Settings


class TOCOnlineError(Exception):
    """Raised when the TOC Online API returns an error payload."""

    def __init__(self, errors: list[dict[str, str]], status_code: int) -> None:
        """Initialise with parsed API error entries and the HTTP status code."""
        self.errors = errors
        self.status_code = status_code

        details = "; ".join(
            f"[{e.get('code', '?')}] {e.get('detail', '')}".strip()
            for e in errors
            if e.get("detail") or e.get("code")
        ) or response_text_fallback(status_code)

        prefix = {
            403: "Permission denied (business rule violation): ",
            404: "Resource not found: ",
            422: "Validation failed: ",
        }.get(status_code, f"HTTP {status_code}: ")

        super().__init__(f"{prefix}{details}")


def response_text_fallback(status_code: int) -> str:
    """Return a human-readable fallback message for a given HTTP status code."""
    return {
        400: "Bad request.",
        401: "Unauthorized — token may be expired.",
        403: "Forbidden.",
        404: "Not found.",
        422: "Unprocessable entity.",
        500: "Internal server error.",
    }.get(status_code, f"HTTP {status_code} error.")


class TOCOnlineClient:
    """Thin async wrapper around httpx for the TOC Online API."""

    JSON_API_CONTENT_TYPE = "application/vnd.api+json"

    def __init__(self, settings: Settings, token_store: TokenStore) -> None:
        """Create a client bound to the given settings and token store."""
        self._settings = settings
        self._token_store = token_store
        self._client = httpx.AsyncClient(
            base_url=settings.base_url,
            timeout=30.0,
            verify=True,
            headers={
                "Accept": "application/json",
                "Content-Type": self.JSON_API_CONTENT_TYPE,
            },
        )

    async def _ensure_token(self) -> None:
        if not self._token_store.is_valid:
            await self._token_store.refresh(self._settings, self._client)

    def _auth_header(self) -> dict[str, str]:
        return {"Authorization": self._token_store.bearer}

    @staticmethod
    def _raise_for_api_errors(response: httpx.Response) -> None:
        """Parse JSON:API error arrays and raise TOCOnlineError when present."""
        if response.is_success:
            return
        try:
            body = response.json()
            errors = body.get("errors", [])
            if not errors and not body:
                errors = [{"code": str(response.status_code), "detail": response.text}]
        except Exception:
            errors = [{"code": str(response.status_code), "detail": response.text}]
        raise TOCOnlineError(errors, response.status_code)

    # Reject paths that contain traversal sequences or non-API characters.
    _SAFE_PATH_RE = re.compile(r"^/api[\w/.-]*$")

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs: Any,
    ) -> Any:
        """Execute a request with automatic token refresh on 401 (single retry)."""
        if not self._SAFE_PATH_RE.match(path) or ".." in path:
            raise ValueError(
                f"Unsafe API path rejected: {path!r}. "
                "Paths must start with /api and contain only alphanumeric, "
                "slash, dot, dash, or underscore characters."
            )
        await self._ensure_token()
        response = await self._client.request(
            method, path, headers=self._auth_header(), **kwargs
        )
        if response.status_code == 401:
            # Token expired mid-session — force refresh and retry once.
            await self._token_store.refresh(self._settings, self._client)
            response = await self._client.request(
                method, path, headers=self._auth_header(), **kwargs
            )
        self._raise_for_api_errors(response)
        return response.json()

    async def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        """Send a GET request and return the parsed JSON response."""
        return await self._request("GET", path, params=params)

    async def post(self, path: str, *, json: Any) -> Any:
        """Send a POST request with a JSON body and return the parsed response."""
        return await self._request("POST", path, json=json)

    async def patch(self, path: str, *, json: Any) -> Any:
        """Send a PATCH request with a JSON body and return the parsed response."""
        return await self._request("PATCH", path, json=json)

    async def delete(self, path: str, *, json: Any = None) -> Any:
        """Send a DELETE request and return the parsed JSON response."""
        return await self._request("DELETE", path, json=json)

    async def aclose(self) -> None:
        """Close the underlying HTTP client connection."""
        await self._client.aclose()

    async def __aenter__(self) -> TOCOnlineClient:
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self.aclose()
