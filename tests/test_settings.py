"""Tests for toconline_mcp.settings: Settings defaults, module parsing,
and singleton."""

from __future__ import annotations

import toconline_mcp.settings as settings_module
from toconline_mcp.settings import Settings, get_settings


def _isolated_settings(monkeypatch, **overrides: object) -> Settings:
    """Return Settings with no env-file and all TOCONLINE_ vars cleared."""
    for key in list(__import__("os").environ):
        if key.startswith("TOCONLINE_"):
            monkeypatch.delenv(key, raising=False)
    return Settings(_env_file=None, **overrides)  # type: ignore[call-arg]


class TestSettingsDefaults:
    """Verify that Settings has the expected default values."""

    def test_default_base_url(self, monkeypatch: object) -> None:
        """Settings() should default to the production base URL."""
        s = _isolated_settings(monkeypatch)
        assert s.base_url == "https://api10.toconline.pt"

    def test_default_oauth_token_url(self, monkeypatch: object) -> None:
        """Settings() should default to the production OAuth token URL."""
        s = _isolated_settings(monkeypatch)
        assert s.oauth_token_url == "https://app10.toconline.pt/oauth/token"

    def test_default_read_only_is_false(self, monkeypatch: object) -> None:
        """Settings() should default read_only to False."""
        s = _isolated_settings(monkeypatch)
        assert s.read_only is False

    def test_default_max_write_calls_per_session(self, monkeypatch: object) -> None:
        """Settings() should default max_write_calls_per_session to 50."""
        s = _isolated_settings(monkeypatch)
        assert s.max_write_calls_per_session == 50

    def test_default_modules_is_none(self, monkeypatch: object) -> None:
        """Settings() should default modules to None (all modules enabled)."""
        s = _isolated_settings(monkeypatch)
        assert s.modules is None


class TestSettingsParseModules:
    """Verify the _parse_modules validator behaviour."""

    def test_parse_modules_none_returns_none(self) -> None:
        """_parse_modules(None) should return None."""
        result = Settings._parse_modules(None)
        assert result is None

    def test_parse_modules_empty_string_returns_none(self) -> None:
        """_parse_modules('') should return None."""
        result = Settings._parse_modules("")
        assert result is None

    def test_parse_modules_single_value(self) -> None:
        """A single module name should be returned as a one-item list."""
        result = Settings._parse_modules("customers")
        assert result == ["customers"]

    def test_parse_modules_comma_separated(self) -> None:
        """Comma-separated string should be split into a list of module names."""
        result = Settings._parse_modules("customers, suppliers, auxiliary")
        assert result == ["customers", "suppliers", "auxiliary"]

    def test_parse_modules_whitespace_trimmed(self) -> None:
        """Surrounding whitespace on each module name should be stripped."""
        result = Settings._parse_modules(" customers , suppliers ")
        assert result == ["customers", "suppliers"]

    def test_parse_modules_list_passthrough(self) -> None:
        """A list value should be returned unchanged."""
        result = Settings._parse_modules(["a", "b"])
        assert result == ["a", "b"]

    def test_parse_modules_via_settings_field(self) -> None:
        """Passing modules= to Settings() should go through the validator."""
        s = Settings(modules="customers,suppliers")
        assert s.modules == ["customers", "suppliers"]


class TestGetSettingsSingleton:
    """Verify that get_settings() behaves as a singleton factory."""

    def test_get_settings_returns_settings_instance(self, monkeypatch: object) -> None:
        """get_settings() should return a Settings instance."""
        monkeypatch.setattr(settings_module, "_settings", None)
        result = get_settings()
        assert isinstance(result, Settings)
        # Restore
        monkeypatch.setattr(settings_module, "_settings", None)

    def test_get_settings_returns_same_instance_on_second_call(
        self, monkeypatch: object
    ) -> None:
        """Two consecutive calls to get_settings() should return the same object."""
        monkeypatch.setattr(settings_module, "_settings", None)
        first = get_settings()
        second = get_settings()
        assert first is second
        # Restore
        monkeypatch.setattr(settings_module, "_settings", None)

    def test_get_settings_singleton_reset(self, monkeypatch: object) -> None:
        """After resetting _settings to None, get_settings() creates a new instance."""
        monkeypatch.setattr(settings_module, "_settings", None)
        first = get_settings()
        monkeypatch.setattr(settings_module, "_settings", None)
        second = get_settings()
        assert isinstance(second, Settings)
        assert first is not second
        # Restore
        monkeypatch.setattr(settings_module, "_settings", None)
