"""Tests for the lifespan() async context manager in toconline_mcp.app.

Covers all three token-resolution priority branches and verifies that the
yielded context always contains an ``api_client`` key.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from toconline_mcp.app import lifespan
from toconline_mcp.settings import Settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings(**overrides: object) -> Settings:
    """Return a Settings instance isolated from .env and environment variables."""
    defaults: dict[str, object] = {
        "base_url": "https://test.example.invalid",
        "access_token": "",
        "client_id": "test-client-id",
        "client_secret": "test-client-secret",
        "refresh_token": "",
        "redirect_uri": "",
        "oauth_token_url": "https://auth.example.invalid/oauth/token",
        "read_only": False,
        "max_write_calls_per_session": 50,
        "modules": None,
    }
    defaults.update(overrides)
    return Settings.model_validate(defaults)


def _make_client_async_context_manager() -> MagicMock:
    """Return a MagicMock that can be used as an async context manager."""
    mock_client = MagicMock()
    inner = MagicMock(name="api_client_instance")
    mock_client.__aenter__ = AsyncMock(return_value=inner)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLifespan:
    """Tests for the lifespan() async context manager."""

    async def test_static_access_token_calls_load_static(self) -> None:
        """Priority 1: when settings.access_token is set, load_static() is called."""
        settings = _make_settings(access_token="static-tok")
        mock_store = MagicMock()
        mock_client = _make_client_async_context_manager()

        with (
            patch("toconline_mcp.app.get_settings", return_value=settings),
            patch("toconline_mcp.app.load_refresh_token", return_value=None),
            patch("toconline_mcp.app.TokenStore", return_value=mock_store),
            patch("toconline_mcp.app.TOCOnlineClient", return_value=mock_client),
        ):
            async with lifespan(MagicMock()) as ctx:
                mock_store.load_static.assert_called_once_with("static-tok")
                mock_store.load_refresh_token.assert_not_called()
                assert "api_client" in ctx

    async def test_keychain_token_calls_load_refresh_token(self) -> None:
        """Priority 2: when the keychain holds a token, load_refresh_token() is called."""
        settings = _make_settings()  # no access_token, no refresh_token in env
        mock_store = MagicMock()
        mock_client = _make_client_async_context_manager()

        with (
            patch("toconline_mcp.app.get_settings", return_value=settings),
            patch(
                "toconline_mcp.app.load_refresh_token",
                return_value="keychain-tok",
            ),
            patch("toconline_mcp.app.TokenStore", return_value=mock_store),
            patch("toconline_mcp.app.TOCOnlineClient", return_value=mock_client),
        ):
            async with lifespan(MagicMock()) as ctx:
                mock_store.load_static.assert_not_called()
                mock_store.load_refresh_token.assert_called_once_with("keychain-tok")
                assert "api_client" in ctx

    async def test_env_refresh_token_fallback_when_no_keychain(self) -> None:
        """Priority 3: when keychain is empty, settings.refresh_token is used."""
        settings = _make_settings(refresh_token="env-refresh-tok")
        mock_store = MagicMock()
        mock_client = _make_client_async_context_manager()

        with (
            patch("toconline_mcp.app.get_settings", return_value=settings),
            patch(
                "toconline_mcp.app.load_refresh_token",
                return_value=None,  # keychain empty
            ),
            patch("toconline_mcp.app.TokenStore", return_value=mock_store),
            patch("toconline_mcp.app.TOCOnlineClient", return_value=mock_client),
        ):
            async with lifespan(MagicMock()) as ctx:
                mock_store.load_static.assert_not_called()
                mock_store.load_refresh_token.assert_called_once_with("env-refresh-tok")
                assert "api_client" in ctx

    async def test_no_tokens_yields_client_without_loading_any_token(self) -> None:
        """When no tokens are present, neither loader is called but ctx still has api_client."""
        settings = _make_settings()  # no access_token, no refresh_token
        mock_store = MagicMock()
        mock_client = _make_client_async_context_manager()

        with (
            patch("toconline_mcp.app.get_settings", return_value=settings),
            patch(
                "toconline_mcp.app.load_refresh_token",
                return_value=None,
            ),
            patch("toconline_mcp.app.TokenStore", return_value=mock_store),
            patch("toconline_mcp.app.TOCOnlineClient", return_value=mock_client),
        ):
            async with lifespan(MagicMock()) as ctx:
                mock_store.load_static.assert_not_called()
                mock_store.load_refresh_token.assert_not_called()
                assert "api_client" in ctx
