"""Tests for toconline_mcp.cli: argument parsing and auth sub-commands."""

from __future__ import annotations

import argparse
from unittest.mock import MagicMock, patch

import pytest

from toconline_mcp.cli import (
    _auth_login,
    _auth_logout,
    _auth_status,
    _build_parser,
    _extract_code,
    _run_auth,
)
from toconline_mcp.settings import Settings


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_settings(**overrides: object) -> Settings:
    """Return a Settings instance with safe test-only values."""
    defaults: dict[str, object] = {
        "base_url": "https://test.example.invalid",
        "access_token": "",
        "client_id": "test-client-id",
        "client_secret": "test-client-secret",
        "refresh_token": "",
        "redirect_uri": "http://localhost/callback",
        "oauth_token_url": "https://auth.example.invalid/token",
        "read_only": False,
        "max_write_calls_per_session": 50,
        "modules": None,
    }
    defaults.update(overrides)
    return Settings.model_validate(defaults)


# ---------------------------------------------------------------------------
# TestExtractCode
# ---------------------------------------------------------------------------


class TestExtractCode:
    """Pure unit tests for _extract_code() — no I/O involved."""

    def test_extract_code_from_url_with_code_param(self) -> None:
        """Full callback URL with ?code= param returns the code value."""
        url = "http://localhost/callback?code=AUTH123&state=abc"
        assert _extract_code(url) == "AUTH123"

    def test_extract_code_from_raw_code_string(self) -> None:
        """A bare code string (no http prefix) is returned as-is."""
        assert _extract_code("AUTH123") == "AUTH123"

    def test_extract_code_empty_string_returns_none(self) -> None:
        """An empty string input returns None."""
        assert _extract_code("") is None

    def test_extract_code_url_without_code_param_returns_none(self) -> None:
        """A URL that has no 'code' query parameter returns None."""
        url = "http://localhost/callback?state=xyz"
        assert _extract_code(url) is None

    def test_extract_code_strips_whitespace(self) -> None:
        """Leading and trailing whitespace is stripped before processing."""
        assert _extract_code("  AUTH123  ") == "AUTH123"

    def test_extract_code_https_url(self) -> None:
        """An https callback URL with a code param returns the code."""
        url = "https://localhost/callback?code=SECURE99"
        assert _extract_code(url) == "SECURE99"


# ---------------------------------------------------------------------------
# TestAuthStatus
# ---------------------------------------------------------------------------


class TestAuthStatus:
    """Tests for _auth_status() output under various token conditions."""

    def test_auth_status_token_in_keychain(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When keychain holds a token, prints a success confirmation."""
        monkeypatch.setattr("toconline_mcp.cli.has_refresh_token", lambda: True)
        _auth_status()
        out = capsys.readouterr().out
        assert "✓ A refresh token is stored" in out

    def test_auth_status_no_keychain_but_env_token(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When keychain is empty but .env has a token, prints a warning."""
        monkeypatch.setattr("toconline_mcp.cli.has_refresh_token", lambda: False)
        settings = _make_settings(refresh_token="tok")
        monkeypatch.setattr("toconline_mcp.cli.get_settings", lambda: settings)
        _auth_status()
        out = capsys.readouterr().out
        assert "⚠ No token in keychain" in out

    def test_auth_status_no_token_anywhere(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When no token exists anywhere, prints an error directing to login."""
        monkeypatch.setattr("toconline_mcp.cli.has_refresh_token", lambda: False)
        settings = _make_settings(refresh_token="")
        monkeypatch.setattr("toconline_mcp.cli.get_settings", lambda: settings)
        _auth_status()
        out = capsys.readouterr().out
        assert "✗ No refresh token found" in out


# ---------------------------------------------------------------------------
# TestAuthLogout
# ---------------------------------------------------------------------------


class TestAuthLogout:
    """Tests for _auth_logout() output based on keychain availability."""

    def test_auth_logout_success(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When deletion succeeds, prints a success message."""
        monkeypatch.setattr("toconline_mcp.cli.delete_refresh_token", lambda: True)
        _auth_logout()
        out = capsys.readouterr().out
        assert "✓ Refresh token removed" in out

    def test_auth_logout_keychain_unavailable(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When keychain backend is unavailable, prints a warning."""
        monkeypatch.setattr("toconline_mcp.cli.delete_refresh_token", lambda: False)
        _auth_logout()
        out = capsys.readouterr().out
        assert "⚠ Could not delete" in out


# ---------------------------------------------------------------------------
# TestBuildParser
# ---------------------------------------------------------------------------


class TestBuildParser:
    """Tests for the ArgumentParser structure returned by _build_parser()."""

    def test_parser_auth_subcommand_exists(self) -> None:
        """Parsing ['auth'] sets command='auth' with both flags False."""
        parser = _build_parser()
        args = parser.parse_args(["auth"])
        assert args.command == "auth"
        assert args.status is False
        assert args.logout is False

    def test_parser_auth_status_flag(self) -> None:
        """Parsing ['auth', '--status'] sets args.status to True."""
        parser = _build_parser()
        args = parser.parse_args(["auth", "--status"])
        assert args.status is True

    def test_parser_auth_logout_flag(self) -> None:
        """Parsing ['auth', '--logout'] sets args.logout to True."""
        parser = _build_parser()
        args = parser.parse_args(["auth", "--logout"])
        assert args.logout is True

    def test_parser_no_subcommand_defaults(self) -> None:
        """Parsing [] (no subcommand) leaves args.command as None."""
        parser = _build_parser()
        args = parser.parse_args([])
        assert args.command is None

    def test_parser_auth_status_and_logout_mutually_exclusive(
        self,
    ) -> None:
        """Passing both --status and --logout raises SystemExit."""
        parser = _build_parser()
        with pytest.raises(SystemExit):
            parser.parse_args(["auth", "--status", "--logout"])


# ---------------------------------------------------------------------------
# TestRunAuth
# ---------------------------------------------------------------------------


class TestRunAuth:
    """Tests for _run_auth() dispatching to the correct sub-handler."""

    def _make_args(
        self, status: bool = False, logout: bool = False
    ) -> argparse.Namespace:
        """Return a minimal Namespace mimicking parsed auth args."""
        return argparse.Namespace(status=status, logout=logout)

    def test_run_auth_calls_status_when_status_flag(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When args.status is True, _auth_status() is called."""
        mock_status = MagicMock()
        monkeypatch.setattr("toconline_mcp.cli._auth_status", mock_status)
        _run_auth(self._make_args(status=True))
        mock_status.assert_called_once()

    def test_run_auth_calls_logout_when_logout_flag(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When args.logout is True, _auth_logout() is called."""
        mock_logout = MagicMock()
        monkeypatch.setattr("toconline_mcp.cli._auth_logout", mock_logout)
        _run_auth(self._make_args(logout=True))
        mock_logout.assert_called_once()

    def test_run_auth_calls_login_by_default(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When both flags are False, _auth_login() is called."""
        mock_login = MagicMock()
        monkeypatch.setattr("toconline_mcp.cli._auth_login", mock_login)
        _run_auth(self._make_args())
        mock_login.assert_called_once()


# ---------------------------------------------------------------------------
# TestAuthLogin
# ---------------------------------------------------------------------------


class TestAuthLogin:
    """Tests for _auth_login() covering each early-exit branch and happy path."""

    def test_auth_login_exits_if_no_client_credentials(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When client_id/secret are missing, prints an error and calls sys.exit(1)."""
        settings = _make_settings(client_id="", client_secret="")
        monkeypatch.setattr("toconline_mcp.cli.get_settings", lambda: settings)
        with pytest.raises(SystemExit) as exc_info:
            _auth_login()
        assert exc_info.value.code == 1
        assert "TOCONLINE_CLIENT_ID" in capsys.readouterr().err

    def test_auth_login_exits_on_csrf_state_mismatch(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When callback URL state does not match expected state, sys.exit(1) is raised."""
        settings = _make_settings()
        monkeypatch.setattr("toconline_mcp.cli.get_settings", lambda: settings)
        monkeypatch.setattr(
            "toconline_mcp.cli.make_auth_url",
            lambda s: ("https://auth.example.invalid/auth", "verifier", "correct"),
        )
        monkeypatch.setattr("toconline_mcp.cli.webbrowser.open", lambda url: None)
        monkeypatch.setattr(
            "builtins.input",
            lambda _: "https://localhost/cb?code=ABC&state=WRONG",
        )
        with pytest.raises(SystemExit) as exc_info:
            _auth_login()
        assert exc_info.value.code == 1
        assert "state mismatch" in capsys.readouterr().err.lower()

    def test_auth_login_exits_when_no_code_extracted(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When user input yields no extractable code, sys.exit(1) is raised."""
        settings = _make_settings()
        monkeypatch.setattr("toconline_mcp.cli.get_settings", lambda: settings)
        monkeypatch.setattr(
            "toconline_mcp.cli.make_auth_url",
            lambda s: ("https://auth.example.invalid/auth", "verifier", "s"),
        )
        monkeypatch.setattr("toconline_mcp.cli.webbrowser.open", lambda url: None)
        # Blank input produces no code.
        monkeypatch.setattr("builtins.input", lambda _: "")
        with pytest.raises(SystemExit) as exc_info:
            _auth_login()
        assert exc_info.value.code == 1

    def test_auth_login_exits_when_no_refresh_token_in_response(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """When exchange response lacks refresh_token, sys.exit(1) is raised."""
        settings = _make_settings()
        monkeypatch.setattr("toconline_mcp.cli.get_settings", lambda: settings)
        monkeypatch.setattr(
            "toconline_mcp.cli.make_auth_url",
            lambda s: ("https://auth.example.invalid/auth", "verifier", "s"),
        )
        monkeypatch.setattr("toconline_mcp.cli.webbrowser.open", lambda url: None)
        monkeypatch.setattr("builtins.input", lambda _: "MYCODE")
        # Exchange returns only an access token — no refresh_token.
        monkeypatch.setattr(
            "toconline_mcp.cli.asyncio.run",
            lambda _coro: {"access_token": "acc", "expires_in": 3600},
        )
        with pytest.raises(SystemExit) as exc_info:
            _auth_login()
        assert exc_info.value.code == 1
        assert "refresh_token" in capsys.readouterr().err

    def test_auth_login_happy_path_stores_token_and_prints_success(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """Happy path: valid code input leads to token exchange, keychain store, and success output."""
        settings = _make_settings()
        monkeypatch.setattr("toconline_mcp.cli.get_settings", lambda: settings)
        monkeypatch.setattr(
            "toconline_mcp.cli.make_auth_url",
            lambda s: ("https://auth.example.invalid/auth", "verifier", "s"),
        )
        monkeypatch.setattr("toconline_mcp.cli.webbrowser.open", lambda url: None)
        monkeypatch.setattr("builtins.input", lambda _: "MYCODE")
        monkeypatch.setattr(
            "toconline_mcp.cli.asyncio.run",
            lambda _coro: {
                "access_token": "acc",
                "refresh_token": "reftok",
                "expires_in": 3600,
            },
        )
        mock_store = MagicMock(return_value=True)
        monkeypatch.setattr("toconline_mcp.cli.store_refresh_token", mock_store)
        _auth_login()
        mock_store.assert_called_once_with("reftok")
        assert "✓" in capsys.readouterr().out
