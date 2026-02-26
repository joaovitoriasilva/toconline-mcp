"""Tests for toconline_mcp.keychain: store, load, delete, and has_refresh_token."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

from toconline_mcp.keychain import (
    delete_refresh_token,
    has_refresh_token,
    load_refresh_token,
    store_refresh_token,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SERVICE = "toconline-mcp"
_KEY = "refresh_token"


def _make_fake_keyring() -> MagicMock:
    """Return a MagicMock that mimics the keyring package structure."""
    fake = MagicMock()
    fake.errors = MagicMock()
    fake.errors.NoKeyringError = type("NoKeyringError", (Exception,), {})
    fake.errors.PasswordDeleteError = type("PasswordDeleteError", (Exception,), {})
    return fake


# ---------------------------------------------------------------------------
# TestStoreRefreshToken
# ---------------------------------------------------------------------------


class TestStoreRefreshToken:
    """Tests for store_refresh_token()."""

    def test_store_returns_true_on_success(self) -> None:
        """store_refresh_token() returns True when set_password succeeds."""
        fake = _make_fake_keyring()
        with patch.dict(sys.modules, {"keyring": fake, "keyring.errors": fake.errors}):
            result = store_refresh_token("my-token")
        assert result is True
        fake.set_password.assert_called_once_with(_SERVICE, _KEY, "my-token")

    def test_store_returns_false_on_no_keyring_error(self) -> None:
        """store_refresh_token() returns False when NoKeyringError is raised."""
        fake = _make_fake_keyring()
        fake.set_password.side_effect = fake.errors.NoKeyringError()
        with patch.dict(sys.modules, {"keyring": fake, "keyring.errors": fake.errors}):
            result = store_refresh_token("my-token")
        assert result is False

    def test_store_returns_false_on_unexpected_exception(self) -> None:
        """store_refresh_token() returns False on any unexpected exception."""
        fake = _make_fake_keyring()
        fake.set_password.side_effect = RuntimeError("unexpected")
        with patch.dict(sys.modules, {"keyring": fake, "keyring.errors": fake.errors}):
            result = store_refresh_token("my-token")
        assert result is False

    def test_store_returns_false_if_keyring_not_installed(self) -> None:
        """store_refresh_token() returns False when keyring is not installed."""
        with patch.dict(sys.modules, {"keyring": None}):
            result = store_refresh_token("my-token")
        assert result is False


# ---------------------------------------------------------------------------
# TestLoadRefreshToken
# ---------------------------------------------------------------------------


class TestLoadRefreshToken:
    """Tests for load_refresh_token()."""

    def test_load_returns_token_when_present(self) -> None:
        """load_refresh_token() returns the token string when one is stored."""
        fake = _make_fake_keyring()
        fake.get_password.return_value = "my-token"
        with patch.dict(sys.modules, {"keyring": fake, "keyring.errors": fake.errors}):
            result = load_refresh_token()
        assert result == "my-token"

    def test_load_returns_none_when_not_found(self) -> None:
        """load_refresh_token() returns None when get_password returns None."""
        fake = _make_fake_keyring()
        fake.get_password.return_value = None
        with patch.dict(sys.modules, {"keyring": fake, "keyring.errors": fake.errors}):
            result = load_refresh_token()
        assert result is None

    def test_load_returns_none_on_no_keyring_error(self) -> None:
        """load_refresh_token() returns None when NoKeyringError is raised."""
        fake = _make_fake_keyring()
        fake.get_password.side_effect = fake.errors.NoKeyringError()
        with patch.dict(sys.modules, {"keyring": fake, "keyring.errors": fake.errors}):
            result = load_refresh_token()
        assert result is None

    def test_load_returns_none_on_unexpected_exception(self) -> None:
        """load_refresh_token() returns None on any unexpected exception."""
        fake = _make_fake_keyring()
        fake.get_password.side_effect = RuntimeError("unexpected")
        with patch.dict(sys.modules, {"keyring": fake, "keyring.errors": fake.errors}):
            result = load_refresh_token()
        assert result is None

    def test_load_returns_none_if_keyring_not_installed(self) -> None:
        """load_refresh_token() returns None when keyring is not installed."""
        with patch.dict(sys.modules, {"keyring": None}):
            result = load_refresh_token()
        assert result is None


# ---------------------------------------------------------------------------
# TestDeleteRefreshToken
# ---------------------------------------------------------------------------


class TestDeleteRefreshToken:
    """Tests for delete_refresh_token()."""

    def test_delete_returns_true_on_success(self) -> None:
        """delete_refresh_token() returns True when delete_password succeeds."""
        fake = _make_fake_keyring()
        with patch.dict(sys.modules, {"keyring": fake, "keyring.errors": fake.errors}):
            result = delete_refresh_token()
        assert result is True
        fake.delete_password.assert_called_once_with(_SERVICE, _KEY)

    def test_delete_returns_true_on_password_delete_error(self) -> None:
        """delete_refresh_token() returns True on PasswordDeleteError (already gone)."""
        fake = _make_fake_keyring()
        fake.delete_password.side_effect = fake.errors.PasswordDeleteError()
        with patch.dict(sys.modules, {"keyring": fake, "keyring.errors": fake.errors}):
            result = delete_refresh_token()
        assert result is True

    def test_delete_returns_false_on_no_keyring_error(self) -> None:
        """delete_refresh_token() returns False when NoKeyringError is raised."""
        fake = _make_fake_keyring()
        fake.delete_password.side_effect = fake.errors.NoKeyringError()
        with patch.dict(sys.modules, {"keyring": fake, "keyring.errors": fake.errors}):
            result = delete_refresh_token()
        assert result is False

    def test_delete_returns_false_on_unexpected_exception(self) -> None:
        """delete_refresh_token() returns False on any unexpected exception."""
        fake = _make_fake_keyring()
        fake.delete_password.side_effect = RuntimeError("unexpected")
        with patch.dict(sys.modules, {"keyring": fake, "keyring.errors": fake.errors}):
            result = delete_refresh_token()
        assert result is False

    def test_delete_returns_false_if_keyring_not_installed(self) -> None:
        """delete_refresh_token() returns False when keyring is not installed."""
        with patch.dict(sys.modules, {"keyring": None}):
            result = delete_refresh_token()
        assert result is False


# ---------------------------------------------------------------------------
# TestHasRefreshToken
# ---------------------------------------------------------------------------


class TestHasRefreshToken:
    """Tests for has_refresh_token()."""

    def test_has_token_true_when_token_exists(self) -> None:
        """has_refresh_token() returns True when a token is stored."""
        fake = _make_fake_keyring()
        fake.get_password.return_value = "some-token"
        with patch.dict(sys.modules, {"keyring": fake, "keyring.errors": fake.errors}):
            result = has_refresh_token()
        assert result is True

    def test_has_token_false_when_no_token(self) -> None:
        """has_refresh_token() returns False when no token is stored."""
        fake = _make_fake_keyring()
        fake.get_password.return_value = None
        with patch.dict(sys.modules, {"keyring": fake, "keyring.errors": fake.errors}):
            result = has_refresh_token()
        assert result is False
