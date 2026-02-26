"""Shared pytest fixtures for the toconline-mcp test suite."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

import toconline_mcp.app as app_module
import toconline_mcp.settings as settings_module
from toconline_mcp.auth import TokenStore
from toconline_mcp.client import TOCOnlineClient
from toconline_mcp.settings import Settings


def make_isolated_settings(**overrides: object) -> Settings:
    """Return a Settings instance isolated from .env and env vars.

    Use this in test files instead of local _make_settings() helpers.
    """
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


@pytest.fixture(autouse=True)
def reset_globals() -> None:
    """Reset global singletons before and after every test.

    Ensures that cached settings and the write-call counter do not
    leak state between tests.
    """
    settings_module._settings = None
    app_module._write_call_count = 0
    yield
    settings_module._settings = None
    app_module._write_call_count = 0


@pytest.fixture
def mock_settings() -> Settings:
    """Return a Settings instance with safe, test-only values.

    Bypasses environment variables and the .env file by constructing
    the model directly via model_validate with the env_prefix disabled.
    """
    return Settings.model_validate(
        {
            "base_url": "https://test.example.invalid",
            "access_token": "test-static-token",
            "client_id": "test-client-id",
            "client_secret": "test-client-secret",
            "refresh_token": "",
            "redirect_uri": "",
            "oauth_token_url": "https://auth.example.invalid/oauth/token",
            "read_only": False,
            "max_write_calls_per_session": 50,
            "modules": None,
        }
    )


@pytest.fixture
def mock_token_store() -> TokenStore:
    """Return a TokenStore pre-loaded with a static test bearer token."""
    store = TokenStore()
    store.load_static("test-bearer-token")
    return store


@pytest.fixture
def mock_api_client() -> MagicMock:
    """Return a MagicMock of TOCOnlineClient with async HTTP methods."""
    client = MagicMock(spec=TOCOnlineClient)
    client.get = AsyncMock(return_value={})
    client.post = AsyncMock(return_value={})
    client.patch = AsyncMock(return_value={})
    client.delete = AsyncMock(return_value={})
    return client


@pytest.fixture
def mock_ctx(mock_api_client: MagicMock) -> MagicMock:
    """Return a MagicMock Context whose lifespan_context holds mock_api_client."""
    ctx = MagicMock()
    ctx.request_context.lifespan_context = {"api_client": mock_api_client}
    return ctx
