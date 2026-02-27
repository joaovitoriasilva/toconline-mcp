"""Tests for toconline_mcp.auth: PKCE helpers, make_auth_url, token exchange,
TokenStore."""

from __future__ import annotations

import base64
import hashlib
import time
from unittest.mock import AsyncMock, MagicMock, patch
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from toconline_mcp.auth import (
    TokenStore,
    _generate_pkce_pair,
    _generate_state,
    exchange_code_for_tokens,
    make_auth_url,
)
from toconline_mcp.settings import Settings

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE64URL_CHARS = set(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
)


def _is_base64url_no_padding(value: str) -> bool:
    """Return True if *value* uses only base64url characters with no padding."""
    return bool(value) and all(c in _BASE64URL_CHARS for c in value)


def _make_test_settings(**overrides: object) -> Settings:
    """Return a Settings instance with safe test values."""
    defaults = {
        "client_id": "test-client",
        "client_secret": "test-secret",
        "oauth_token_url": "https://example.com/oauth/token",
        "redirect_uri": "",
    }
    defaults.update(overrides)
    return Settings(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# TestGeneratePkce
# ---------------------------------------------------------------------------


class TestGeneratePkce:
    """Tests for the internal _generate_pkce_pair() helper."""

    def test_pkce_pair_returns_two_strings(self) -> None:
        """_generate_pkce_pair() must return a 2-tuple of strings."""
        result = _generate_pkce_pair()
        assert isinstance(result, tuple)
        assert len(result) == 2
        verifier, challenge = result
        assert isinstance(verifier, str)
        assert isinstance(challenge, str)

    def test_pkce_verifier_is_base64url_no_padding(self) -> None:
        """The code_verifier must use only base64url chars without padding."""
        verifier, _ = _generate_pkce_pair()
        assert _is_base64url_no_padding(verifier)
        assert "=" not in verifier

    def test_pkce_challenge_is_base64url_no_padding(self) -> None:
        """The code_challenge must use only base64url chars without padding."""
        _, challenge = _generate_pkce_pair()
        assert _is_base64url_no_padding(challenge)
        assert "=" not in challenge

    def test_pkce_challenge_is_sha256_of_verifier(self) -> None:
        """code_challenge must equal base64url(SHA256(verifier)) without padding."""
        verifier, challenge = _generate_pkce_pair()
        digest = hashlib.sha256(verifier.encode()).digest()
        expected = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
        assert challenge == expected

    def test_pkce_pair_differs_each_call(self) -> None:
        """Two successive calls should yield different code verifiers."""
        verifier1, _ = _generate_pkce_pair()
        verifier2, _ = _generate_pkce_pair()
        assert verifier1 != verifier2


# ---------------------------------------------------------------------------
# TestGenerateState
# ---------------------------------------------------------------------------


class TestGenerateState:
    """Tests for the internal _generate_state() helper."""

    def test_state_is_string(self) -> None:
        """_generate_state() must return a str."""
        state = _generate_state()
        assert isinstance(state, str)

    def test_state_is_base64url_no_padding(self) -> None:
        """State must use only base64url chars without padding."""
        state = _generate_state()
        assert _is_base64url_no_padding(state)
        assert "=" not in state

    def test_state_differs_each_call(self) -> None:
        """Two successive calls should yield different state values."""
        assert _generate_state() != _generate_state()


# ---------------------------------------------------------------------------
# TestMakeAuthUrl
# ---------------------------------------------------------------------------


class TestMakeAuthUrl:
    """Tests for make_auth_url()."""

    def test_make_auth_url_returns_three_values(self) -> None:
        """make_auth_url() must return a 3-tuple."""
        settings = _make_test_settings()
        result = make_auth_url(settings)
        assert isinstance(result, tuple)
        assert len(result) == 3

    def test_auth_url_contains_required_params(self) -> None:
        """The auth URL must contain all required OAuth2/PKCE query params."""
        settings = _make_test_settings()
        url, _verifier, _state = make_auth_url(settings)
        assert "client_id=test-client" in url
        assert "response_type=code" in url
        assert "scope=commercial" in url
        assert "code_challenge_method=S256" in url
        assert "code_challenge=" in url

    def test_auth_url_uses_auth_endpoint(self) -> None:
        """The '/token' segment in oauth_token_url must be replaced with '/auth'."""
        settings = _make_test_settings(
            oauth_token_url="https://example.com/oauth/token"
        )
        url, _, _ = make_auth_url(settings)
        assert "/oauth/auth" in url
        assert "/oauth/token" not in url

    def test_auth_url_uses_default_redirect_uri(self) -> None:
        """When redirect_uri is empty, the Postman callback URI should be used."""
        settings = _make_test_settings(redirect_uri="")
        url, _, _ = make_auth_url(settings)
        query = parse_qs(urlparse(url).query)
        redirect_uri = query.get("redirect_uri", [""])[0]
        assert urlparse(redirect_uri).hostname == "oauth.pstmn.io"

    def test_auth_url_uses_configured_redirect_uri(self) -> None:
        """When redirect_uri is set in settings, it must appear in the URL."""
        settings = _make_test_settings(redirect_uri="https://myapp.com/callback")
        url, _, _ = make_auth_url(settings)
        query = parse_qs(urlparse(url).query)
        redirect_uri = query.get("redirect_uri", [""])[0]
        assert urlparse(redirect_uri).hostname == "myapp.com"


# ---------------------------------------------------------------------------
# TestExchangeCodeForTokens
# ---------------------------------------------------------------------------


class TestExchangeCodeForTokens:
    """Tests for exchange_code_for_tokens()."""

    async def test_exchange_posts_correct_body_and_returns_token(self) -> None:
        """Successful exchange should return the parsed token dict."""
        token_payload = {
            "access_token": "access-abc",
            "refresh_token": "refresh-xyz",
            "expires_in": 7890000,
        }
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = token_payload

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)

        settings = _make_test_settings()
        result = await exchange_code_for_tokens(
            code="auth-code-123",
            code_verifier="verifier-abc",
            settings=settings,
            client=mock_client,
        )

        assert result == token_payload
        mock_client.post.assert_awaited_once()

    async def test_exchange_raises_on_http_error(self) -> None:
        """A 401 response should cause raise_for_status to raise HTTPStatusError."""
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "401 Unauthorised",
            request=MagicMock(),
            response=MagicMock(),
        )

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)

        settings = _make_test_settings()
        with pytest.raises(httpx.HTTPStatusError):
            await exchange_code_for_tokens(
                code="bad-code",
                code_verifier="verifier",
                settings=settings,
                client=mock_client,
            )


# ---------------------------------------------------------------------------
# TestTokenStore
# ---------------------------------------------------------------------------


class TestTokenStore:
    """Tests for the TokenStore dataclass."""

    # ------------------------------------------------------------------
    # load_static / basic validity
    # ------------------------------------------------------------------

    def test_load_static_sets_token_and_infinite_expiry(self) -> None:
        """load_static() should make is_valid True and bearer correctly formatted."""
        store = TokenStore()
        store.load_static("my-static-token")
        assert store.is_valid is True
        assert store.bearer == "Bearer my-static-token"

    def test_is_valid_false_when_no_token(self) -> None:
        """A freshly created TokenStore should not be valid."""
        store = TokenStore()
        assert store.is_valid is False

    def test_is_valid_false_when_token_expired(self) -> None:
        """A token whose expiry is in the past should not be valid."""
        store = TokenStore()
        store._access_token = "old-token"
        store._expires_at = time.time() - 1
        assert store.is_valid is False

    def test_is_valid_true_when_well_within_expiry(self) -> None:
        """A token with ample time remaining should be valid."""
        store = TokenStore()
        store._access_token = "fresh-token"
        store._expires_at = time.time() + 7200
        assert store.is_valid is True

    def test_is_valid_false_within_60s_buffer(self) -> None:
        """A token expiring within the 60-second buffer should be invalid."""
        store = TokenStore()
        store._access_token = "almost-expired"
        store._expires_at = time.time() + 30  # within 60s buffer
        assert store.is_valid is False

    # ------------------------------------------------------------------
    # bearer
    # ------------------------------------------------------------------

    def test_bearer_format(self) -> None:
        """bearer property should return 'Bearer <token>'."""
        store = TokenStore()
        store._access_token = "tok123"
        assert store.bearer == "Bearer tok123"

    # ------------------------------------------------------------------
    # load_refresh_token
    # ------------------------------------------------------------------

    def test_load_refresh_token_stores_token(self) -> None:
        """load_refresh_token() should persist the token for later refresh use."""
        store = TokenStore()
        store.load_refresh_token("refresh-abc")
        assert store._refresh_token == "refresh-abc"

    # ------------------------------------------------------------------
    # refresh - error paths
    # ------------------------------------------------------------------

    async def test_refresh_raises_if_no_client_credentials(self) -> None:
        """RuntimeError raised when client_id/secret are both empty."""
        store = TokenStore()
        settings = Settings(_env_file=None, client_id="", client_secret="")
        mock_client = MagicMock(spec=httpx.AsyncClient)
        with pytest.raises(RuntimeError, match="TOCONLINE_ACCESS_TOKEN"):
            await store.refresh(settings, mock_client)

    async def test_refresh_raises_if_no_refresh_token(self) -> None:
        """RuntimeError raised when client creds exist but no refresh token."""
        store = TokenStore()
        settings = Settings(
            _env_file=None,
            client_id="cid",
            client_secret="csec",
            refresh_token="",
        )
        mock_client = MagicMock(spec=httpx.AsyncClient)
        with pytest.raises(RuntimeError, match="refresh_token"):
            await store.refresh(settings, mock_client)

    # ------------------------------------------------------------------
    # refresh - success paths
    # ------------------------------------------------------------------

    def _make_mock_client(self, json_payload: dict) -> MagicMock:
        """Return an httpx.AsyncClient mock with post returning *json_payload*."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = json_payload

        mock_client = MagicMock(spec=httpx.AsyncClient)
        mock_client.post = AsyncMock(return_value=mock_response)
        return mock_client

    async def test_refresh_updates_access_token(self) -> None:
        """After a successful refresh, _access_token should be updated."""
        store = TokenStore()
        settings = Settings(
            _env_file=None,
            client_id="cid",
            client_secret="csec",
            refresh_token="old-refresh",
        )
        mock_client = self._make_mock_client(
            {"access_token": "new-access", "expires_in": 3600}
        )
        before = time.time()
        await store.refresh(settings, mock_client)
        after = time.time()

        assert store._access_token == "new-access"
        assert before + 3600 - 5 <= store._expires_at <= after + 3600 + 5

    async def test_refresh_stores_new_refresh_token_in_keychain(
        self,
    ) -> None:
        """When response includes refresh_token, store_refresh_token is called."""
        store = TokenStore()
        settings = Settings(
            _env_file=None,
            client_id="cid",
            client_secret="csec",
            refresh_token="old-refresh",
        )
        mock_client = self._make_mock_client(
            {
                "access_token": "new-access",
                "expires_in": 3600,
                "refresh_token": "new-refresh",
            }
        )
        with patch("toconline_mcp.keychain.store_refresh_token") as mock_store:
            await store.refresh(settings, mock_client)
            mock_store.assert_called_once_with("new-refresh")

    async def test_refresh_updates_internal_refresh_token(self) -> None:
        """When response includes refresh_token, _refresh_token is updated."""
        store = TokenStore()
        settings = Settings(
            _env_file=None,
            client_id="cid",
            client_secret="csec",
            refresh_token="old-refresh",
        )
        mock_client = self._make_mock_client(
            {
                "access_token": "new-access",
                "expires_in": 3600,
                "refresh_token": "brand-new-refresh",
            }
        )
        with patch("toconline_mcp.keychain.store_refresh_token"):
            await store.refresh(settings, mock_client)

        assert store._refresh_token == "brand-new-refresh"
