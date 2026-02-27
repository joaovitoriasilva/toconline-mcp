"""Tests for toconline_mcp.client module.

Covers TOCOnlineError formatting, response_text_fallback, the safe-path
regex, and the full async request lifecycle of TOCOnlineClient.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from toconline_mcp.auth import TokenStore
from toconline_mcp.client import (
    TOCOnlineClient,
    TOCOnlineError,
    response_text_fallback,
)
from toconline_mcp.settings import Settings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings() -> Settings:
    """Return a minimal Settings instance suitable for unit tests."""
    return Settings.model_validate(
        {
            "base_url": "https://test.example.invalid",
            "access_token": "fake-token",
            "client_id": "",
            "client_secret": "",
            "refresh_token": "",
            "redirect_uri": "",
            "oauth_token_url": "https://auth.example.invalid/oauth/token",
            "read_only": False,
            "max_write_calls_per_session": 50,
            "modules": None,
        }
    )


def _make_token_store() -> TokenStore:
    """Return a TokenStore with a static test token loaded."""
    store = TokenStore()
    store.load_static("test-bearer-token")
    return store


def _make_client() -> TOCOnlineClient:
    """Construct a TOCOnlineClient backed by test settings and token store."""
    return TOCOnlineClient(_make_settings(), _make_token_store())


# ---------------------------------------------------------------------------
# TestTOCOnlineError
# ---------------------------------------------------------------------------


class TestTOCOnlineError:
    """Unit tests for TOCOnlineError message formatting."""

    def test_error_formats_code_and_detail(self) -> None:
        """Errors with both 'code' and 'detail' produce a [code] detail message."""
        errors = [{"code": "NOT_FOUND", "detail": "Record missing"}]
        exc = TOCOnlineError(errors, 404)
        assert "[NOT_FOUND]" in str(exc)
        assert "Record missing" in str(exc)

    def test_error_with_missing_detail(self) -> None:
        """An error containing only 'code' (no 'detail') is still included."""
        errors = [{"code": "ERR_CODE"}]
        exc = TOCOnlineError(errors, 400)
        assert "[ERR_CODE]" in str(exc)

    def test_error_with_missing_code(self) -> None:
        """An error containing only 'detail' (no 'code') is still included."""
        errors = [{"detail": "Something went wrong"}]
        exc = TOCOnlineError(errors, 500)
        assert "Something went wrong" in str(exc)

    def test_error_empty_errors_falls_back_to_status_text(self) -> None:
        """An empty errors list falls back to response_text_fallback output."""
        exc = TOCOnlineError([], 404)
        assert "Not found" in str(exc)

    def test_error_403_prefix(self) -> None:
        """Status 403 produces the 'Permission denied (business rule violation)'
        prefix."""
        errors = [{"code": "FORBIDDEN", "detail": "Access denied"}]
        exc = TOCOnlineError(errors, 403)
        assert str(exc).startswith("Permission denied (business rule violation): ")

    def test_error_404_prefix(self) -> None:
        """Status 404 produces the 'Resource not found' prefix."""
        errors = [{"code": "MISSING", "detail": "Gone"}]
        exc = TOCOnlineError(errors, 404)
        assert str(exc).startswith("Resource not found: ")

    def test_error_422_prefix(self) -> None:
        """Status 422 produces the 'Validation failed' prefix."""
        errors = [{"code": "INVALID", "detail": "Bad value"}]
        exc = TOCOnlineError(errors, 422)
        assert str(exc).startswith("Validation failed: ")

    def test_error_unknown_status_uses_generic_prefix(self) -> None:
        """An unrecognised status code produces the 'HTTP <code>' prefix."""
        errors = [{"code": "INTERNAL", "detail": "Boom"}]
        exc = TOCOnlineError(errors, 500)
        assert str(exc).startswith("HTTP 500: ")


# ---------------------------------------------------------------------------
# TestResponseTextFallback
# ---------------------------------------------------------------------------


class TestResponseTextFallback:
    """Parameterised tests for response_text_fallback."""

    @pytest.mark.parametrize(
        "status_code, expected_fragment",
        [
            (400, "Bad request"),
            (401, "Unauthorized"),
            (403, "Forbidden"),
            (404, "Not found"),
            (422, "Unprocessable entity"),
            (500, "Internal server error"),
            (418, "HTTP 418"),  # unknown code falls back to generic template
        ],
    )
    def test_fallback_text(self, status_code: int, expected_fragment: str) -> None:
        """response_text_fallback returns the expected text for known and unknown
        codes."""
        result = response_text_fallback(status_code)
        assert expected_fragment in result


# ---------------------------------------------------------------------------
# TestSafePathRegex
# ---------------------------------------------------------------------------


class TestSafePathRegex:
    """Behaviour tests for the URL-safety guard in TOCOnlineClient._request.

    Every assertion is made through the *production* client.get() code path
    rather than against a locally-redefined copy of the regex, ensuring that
    any change to the validation logic in client.py is caught immediately.
    """

    @pytest.mark.parametrize(
        "path",
        [
            "/api/customers",
            "/api/customers/123",
            "/api/v1/sales",
            "/api/items.json",
            "/api/foo-bar_baz",
        ],
    )
    async def test_valid_paths_do_not_raise(self, path: str) -> None:
        """Accepted paths reach the HTTP layer without raising ValueError."""
        client = _make_client()
        mock_http = MagicMock()
        mock_http.request = AsyncMock(return_value=httpx.Response(200, json={}))
        client._client = mock_http
        # Should not raise — the request flows through to the mock HTTP layer.
        await client.get(path)
        mock_http.request.assert_awaited_once()

    @pytest.mark.parametrize(
        "path",
        [
            "/etc/passwd",
            "../secrets",
            "",
            "/customers",
            "/api/foo?bar=1",  # query chars not in [\w/.-]
            "/api/../etc/passwd",  # path-traversal via .. within /api prefix
        ],
    )
    async def test_invalid_paths_raise_value_error(self, path: str) -> None:
        """Rejected paths raise ValueError before any HTTP request is sent."""
        client = _make_client()
        mock_http = MagicMock()
        mock_http.request = AsyncMock(return_value=httpx.Response(200, json={}))
        client._client = mock_http
        with pytest.raises(ValueError, match="Unsafe API path"):
            await client.get(path)
        mock_http.request.assert_not_awaited()


# ---------------------------------------------------------------------------
# TestTOCOnlineClient
# ---------------------------------------------------------------------------


class TestTOCOnlineClient:
    """Async integration-style tests for TOCOnlineClient._request and helpers.

    HTTP calls are intercepted by replacing the internal ``_client`` attribute
    with an AsyncMock after object construction, eliminating real network I/O.
    """

    async def test_request_valid_path_returns_json(self) -> None:
        """A valid /api path with a 200 response returns the parsed JSON body."""
        client = _make_client()
        mock_http = MagicMock()
        mock_http.request = AsyncMock(
            return_value=httpx.Response(200, json={"data": "ok"})
        )
        client._client = mock_http

        result = await client.get("/api/customers")

        assert result == {"data": "ok"}

    async def test_request_invalid_path_raises_value_error(self) -> None:
        """A path that does not start with /api raises ValueError immediately."""
        client = _make_client()

        with pytest.raises(ValueError, match="Unsafe API path rejected"):
            await client.get("/etc/passwd")

    async def test_request_401_triggers_token_refresh_and_retry(self) -> None:
        """A 401 response triggers one token refresh and exactly two HTTP requests."""
        token_store = _make_token_store()
        token_store.refresh = AsyncMock()  # type: ignore[method-assign]

        client = TOCOnlineClient(_make_settings(), token_store)
        mock_http = MagicMock()
        mock_http.request = AsyncMock(
            side_effect=[
                httpx.Response(401, json={}),
                httpx.Response(200, json={"retried": True}),
            ]
        )
        client._client = mock_http

        result = await client.get("/api/customers")

        # Refresh called exactly once after the 401.
        token_store.refresh.assert_awaited_once()
        # Two HTTP requests total: the original and the retry.
        assert mock_http.request.await_count == 2
        assert result == {"retried": True}

    async def test_request_raises_toc_online_error_on_api_error(self) -> None:
        """A 422 response with an errors array raises TOCOnlineError."""
        client = _make_client()
        mock_http = MagicMock()
        mock_http.request = AsyncMock(
            return_value=httpx.Response(
                422,
                json={"errors": [{"code": "INVALID", "detail": "Bad value"}]},
            )
        )
        client._client = mock_http

        with pytest.raises(TOCOnlineError) as exc_info:
            await client.post("/api/customers", json={"name": "x"})

        assert exc_info.value.status_code == 422

    async def test_get_passes_params(self) -> None:
        """get() forwards the params dict to _request as query parameters."""
        client = _make_client()
        mock_http = MagicMock()
        mock_http.request = AsyncMock(
            return_value=httpx.Response(200, json={"results": []})
        )
        client._client = mock_http

        await client.get("/api/customers", params={"page": "1"})

        _, call_kwargs = mock_http.request.call_args
        assert call_kwargs.get("params") == {"page": "1"}

    async def test_post_passes_json_body(self) -> None:
        """post() forwards the json payload to _request."""
        client = _make_client()
        mock_http = MagicMock()
        mock_http.request = AsyncMock(
            return_value=httpx.Response(201, json={"id": "42"})
        )
        client._client = mock_http

        await client.post("/api/customers", json={"name": "ACME"})

        _, call_kwargs = mock_http.request.call_args
        assert call_kwargs.get("json") == {"name": "ACME"}

    async def test_patch_passes_json_body(self) -> None:
        """patch() forwards the json payload to _request."""
        client = _make_client()
        mock_http = MagicMock()
        mock_http.request = AsyncMock(
            return_value=httpx.Response(200, json={"id": "42"})
        )
        client._client = mock_http

        await client.patch("/api/customers/42", json={"name": "Updated"})

        _, call_kwargs = mock_http.request.call_args
        assert call_kwargs.get("json") == {"name": "Updated"}

    async def test_delete_passes_json_body(self) -> None:
        """delete() forwards the optional json payload to _request."""
        client = _make_client()
        mock_http = MagicMock()
        mock_http.request = AsyncMock(return_value=httpx.Response(200, json={}))
        client._client = mock_http

        await client.delete("/api/customers/42", json={"confirm": True})

        _, call_kwargs = mock_http.request.call_args
        assert call_kwargs.get("json") == {"confirm": True}

    async def test_aclose_closes_httpx_client(self) -> None:
        """aclose() delegates to the underlying httpx.AsyncClient.aclose()."""
        client = _make_client()
        mock_http = MagicMock()
        mock_http.aclose = AsyncMock()
        client._client = mock_http

        await client.aclose()

        mock_http.aclose.assert_awaited_once()

    async def test_context_manager_closes_on_exit(self) -> None:
        """Using TOCOnlineClient as an async context manager closes it on exit."""
        client = _make_client()
        mock_http = MagicMock()
        mock_http.aclose = AsyncMock()
        client._client = mock_http

        async with client:
            pass

        mock_http.aclose.assert_awaited_once()
