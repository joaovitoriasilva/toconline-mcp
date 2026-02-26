"""Shared fixtures for the tools test sub-package.

Extends the root conftest fixtures to make ``ctx.error`` and ``ctx.info``
proper ``AsyncMock``s (they are awaited inside every tool function) and
provides a ``patch_settings`` fixture to satisfy the ``write_tool`` decorator's
``get_settings()`` call with a non-read-only Settings instance.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


@pytest.fixture
def mock_ctx(mock_ctx):  # noqa: F811 — intentionally shadows the root fixture
    """Override mock_ctx so async ctx methods (error, info) are awaitable."""
    mock_ctx.error = AsyncMock()
    mock_ctx.info = AsyncMock()
    return mock_ctx


@pytest.fixture
def patch_settings(mock_settings, monkeypatch):
    """Patch ``toconline_mcp.app.get_settings`` to return safe, writable settings.

    Required for every write-tool test so that the ``write_tool`` decorator
    does not reject the call due to read-only mode or missing configuration.
    """
    monkeypatch.setattr("toconline_mcp.app.get_settings", lambda: mock_settings)
    return mock_settings
