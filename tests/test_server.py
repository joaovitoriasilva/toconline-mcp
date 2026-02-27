"""Tests for toconline_mcp.server: tool-module loading logic."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from toconline_mcp.server import _ALL_MODULES, _load_tool_modules
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
        "redirect_uri": "",
        "oauth_token_url": "https://auth.example.invalid/token",
        "read_only": False,
        "max_write_calls_per_session": 50,
        "modules": None,
    }
    defaults.update(overrides)
    return Settings.model_validate(defaults)


# ---------------------------------------------------------------------------
# TestLoadToolModules
# ---------------------------------------------------------------------------


class TestLoadToolModules:
    """Tests for _load_tool_modules() module discovery and validation."""

    def test_loads_all_modules_when_none_configured(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When settings.modules is None, all 11 tool modules are imported."""
        settings = _make_settings(modules=None)
        monkeypatch.setattr("toconline_mcp.server.get_settings", lambda: settings)
        mock_import = MagicMock()
        monkeypatch.setattr("toconline_mcp.server.importlib.import_module", mock_import)

        _load_tool_modules()

        assert mock_import.call_count == 11
        for name in _ALL_MODULES:
            mock_import.assert_any_call(f"toconline_mcp.tools.{name}")

    def test_loads_only_specified_modules(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When settings.modules lists two names, only those two are imported."""
        settings = _make_settings(modules=["customers", "auxiliary"])
        monkeypatch.setattr("toconline_mcp.server.get_settings", lambda: settings)
        mock_import = MagicMock()
        monkeypatch.setattr("toconline_mcp.server.importlib.import_module", mock_import)

        _load_tool_modules()

        assert mock_import.call_count == 2
        mock_import.assert_any_call("toconline_mcp.tools.customers")
        mock_import.assert_any_call("toconline_mcp.tools.auxiliary")

    def test_raises_value_error_for_unknown_module(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unrecognised module name raises ValueError naming the bad module."""
        settings = _make_settings(modules=["nonexistent"])
        monkeypatch.setattr("toconline_mcp.server.get_settings", lambda: settings)
        mock_import = MagicMock()
        monkeypatch.setattr("toconline_mcp.server.importlib.import_module", mock_import)

        with pytest.raises(ValueError, match="nonexistent"):
            _load_tool_modules()

    def test_raises_value_error_lists_valid_names(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The ValueError message contains the list of valid module names."""
        settings = _make_settings(modules=["badmod"])
        monkeypatch.setattr("toconline_mcp.server.get_settings", lambda: settings)
        mock_import = MagicMock()
        monkeypatch.setattr("toconline_mcp.server.importlib.import_module", mock_import)

        with pytest.raises(ValueError, match="customers"):
            _load_tool_modules()

    def test_valid_module_names_include_all_11(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Passing every known module name individually raises no ValueError."""
        mock_import = MagicMock()
        monkeypatch.setattr("toconline_mcp.server.importlib.import_module", mock_import)

        for name in _ALL_MODULES:
            settings = _make_settings(modules=[name])
            monkeypatch.setattr(
                "toconline_mcp.server.get_settings", lambda s=settings: s
            )
            # Should not raise
            _load_tool_modules()
