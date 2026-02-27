"""Tests for toconline_mcp.app module.

Covers the write_tool safety decorator (read-only guard, rate limiting)
and the _build_instructions helper.
"""

from __future__ import annotations

import toconline_mcp.app as app_module
from toconline_mcp.app import _build_instructions, write_tool
from toconline_mcp.settings import Settings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _settings(
    *,
    read_only: bool = False,
    max_write_calls_per_session: int = 50,
) -> Settings:
    """Return a Settings instance with controlled values for testing."""
    return Settings.model_validate(
        {
            "base_url": "https://test.example.invalid",
            "access_token": "tok",
            "client_id": "",
            "client_secret": "",
            "refresh_token": "",
            "redirect_uri": "",
            "oauth_token_url": "https://auth.example.invalid/oauth/token",
            "read_only": read_only,
            "max_write_calls_per_session": max_write_calls_per_session,
            "modules": None,
        }
    )


# ---------------------------------------------------------------------------
# write_tool decorator
# ---------------------------------------------------------------------------


class TestWriteTool:
    """Tests for the write_tool decorator that enforces safety guards."""

    async def test_write_tool_passes_through_when_not_read_only(
        self, monkeypatch
    ) -> None:
        """When read_only=False the underlying function is called and its result
        returned."""
        monkeypatch.setattr(app_module.mcp, "tool", lambda: lambda f: f)
        monkeypatch.setattr(
            "toconline_mcp.app.get_settings",
            lambda: _settings(read_only=False),
        )

        @write_tool
        async def my_tool() -> dict:
            return {"status": "created"}

        result = await my_tool()
        assert result == {"status": "created"}

    async def test_write_tool_blocked_in_read_only_mode(self, monkeypatch) -> None:
        """When read_only=True the wrapper returns an error and never calls the tool."""
        monkeypatch.setattr(app_module.mcp, "tool", lambda: lambda f: f)
        monkeypatch.setattr(
            "toconline_mcp.app.get_settings",
            lambda: _settings(read_only=True),
        )

        invocations: list[int] = []

        @write_tool
        async def my_tool() -> dict:
            invocations.append(1)
            return {"status": "created"}

        result = await my_tool()

        assert "error" in result
        assert "read-only" in result["error"].lower()
        assert invocations == [], (
            "Underlying function must not be called in read-only mode"
        )

    async def test_write_tool_rate_limit_exceeded(self, monkeypatch) -> None:
        """With max_write_calls_per_session=1 the first call succeeds; subsequent
        calls fail."""
        monkeypatch.setattr(app_module.mcp, "tool", lambda: lambda f: f)
        monkeypatch.setattr(
            "toconline_mcp.app.get_settings",
            lambda: _settings(max_write_calls_per_session=1),
        )

        @write_tool
        async def my_tool() -> dict:
            return {"ok": True}

        result1 = await my_tool()
        assert result1 == {"ok": True}, "First call should succeed"

        result2 = await my_tool()
        assert "error" in result2
        assert "rate limit" in result2["error"].lower()

        result3 = await my_tool()
        assert "error" in result3
        assert "rate limit" in result3["error"].lower()

    async def test_write_tool_rate_limit_disabled_when_zero(self, monkeypatch) -> None:
        """When max_write_calls_per_session=0 the rate limit is disabled and all
        calls succeed."""
        monkeypatch.setattr(app_module.mcp, "tool", lambda: lambda f: f)
        monkeypatch.setattr(
            "toconline_mcp.app.get_settings",
            lambda: _settings(max_write_calls_per_session=0),
        )

        @write_tool
        async def my_tool() -> dict:
            return {"ok": True}

        for _ in range(10):
            result = await my_tool()
            assert result == {"ok": True}


# ---------------------------------------------------------------------------
# _build_instructions
# ---------------------------------------------------------------------------


class TestBuildInstructions:
    """Tests for _build_instructions() which generates the MCP server prompt."""

    def test_build_instructions_no_read_only_flag(self, monkeypatch) -> None:
        """When read_only=False the instructions do not mention READ-ONLY."""
        monkeypatch.setattr(
            "toconline_mcp.app.get_settings",
            lambda: _settings(read_only=False),
        )

        instructions = _build_instructions()

        assert "READ-ONLY" not in instructions

    def test_build_instructions_read_only_includes_warning(self, monkeypatch) -> None:
        """When read_only=True the instructions contain the READ-ONLY warning."""
        monkeypatch.setattr(
            "toconline_mcp.app.get_settings",
            lambda: _settings(read_only=True),
        )

        instructions = _build_instructions()

        assert "READ-ONLY" in instructions
