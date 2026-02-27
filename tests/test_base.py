"""Tests for toconline_mcp.tools._base module.

Covers validate_resource_id (input sanitisation) and get_client
(lifespan-context accessor).
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from toconline_mcp.tools._base import get_client, validate_resource_id

# ---------------------------------------------------------------------------
# TestValidateResourceId
# ---------------------------------------------------------------------------


class TestValidateResourceId:
    """Tests for validate_resource_id — the numeric-ID sanitiser."""

    @pytest.mark.parametrize(
        "value",
        [
            "1",
            "42",
            "12345678901234567890",  # 20 digits — maximum allowed length
        ],
    )
    def test_valid_numeric_ids(self, value: str) -> None:
        """Valid numeric strings (1-20 digits) are accepted without error."""
        result = validate_resource_id(value)
        assert result == value

    def test_returns_the_value_unchanged(self) -> None:
        """validate_resource_id returns the exact string passed in."""
        assert validate_resource_id("99") == "99"

    def test_invalid_empty_string(self) -> None:
        """An empty string raises ToolError."""
        with pytest.raises(ToolError):
            validate_resource_id("")

    def test_invalid_with_letters(self) -> None:
        """A string mixing letters and digits raises ToolError."""
        with pytest.raises(ToolError):
            validate_resource_id("abc123")

    def test_invalid_path_traversal(self) -> None:
        """A string containing a slash (path traversal attempt) raises ToolError."""
        with pytest.raises(ToolError):
            validate_resource_id("123/456")

    def test_invalid_too_long(self) -> None:
        """A 21-digit string exceeds the 20-digit maximum and raises ToolError."""
        with pytest.raises(ToolError):
            validate_resource_id("1" * 21)

    def test_invalid_float_string(self) -> None:
        """A decimal string (e.g. '1.5') raises ToolError."""
        with pytest.raises(ToolError):
            validate_resource_id("1.5")

    def test_invalid_negative(self) -> None:
        """A negative number string raises ToolError."""
        with pytest.raises(ToolError):
            validate_resource_id("-1")

    def test_custom_name_in_error_message(self) -> None:
        """When a custom name is provided it appears in the ToolError message."""
        with pytest.raises(ToolError, match="customer_id"):
            validate_resource_id("bad!", name="customer_id")


# ---------------------------------------------------------------------------
# TestGetClient
# ---------------------------------------------------------------------------


class TestGetClient:
    """Tests for get_client — the lifespan-context accessor."""

    def test_get_client_returns_api_client(
        self, mock_ctx: MagicMock, mock_api_client: MagicMock
    ) -> None:
        """get_client extracts the TOCOnlineClient from the request context."""
        result = get_client(mock_ctx)
        assert result is mock_api_client
