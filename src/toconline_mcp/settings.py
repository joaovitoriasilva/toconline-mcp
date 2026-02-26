"""Application settings loaded from environment variables."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """TOC Online MCP server configuration."""

    model_config = SettingsConfigDict(
        env_prefix="TOCONLINE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    base_url: str = "https://api10.toconline.pt"
    """Base URL of the TOC Online API (base_url in the Postman collection)."""

    access_token: str = ""
    """Static Bearer access token. Used directly if provided, otherwise OAuth2 flow is used."""

    client_id: str = ""
    """OAuth2 client ID."""

    client_secret: str = ""
    """OAuth2 client secret."""

    refresh_token: str = ""
    """OAuth2 refresh token obtained from the initial authorization_code+PKCE flow.
    Used to automatically renew expired access tokens without user interaction.
    Set via TOCONLINE_REFRESH_TOKEN in your .env file."""

    redirect_uri: str = ""
    """OAuth2 redirect URI. Defaults to https://oauth.pstmn.io/v1/callback when unset."""

    oauth_token_url: str = "https://app10.toconline.pt/oauth/token"
    """OAuth2 token endpoint (base_url_oauth/token from Postman collection).
    The /auth endpoint is derived by replacing /token with /auth."""

    read_only: bool = False
    """When True, all write operations (POST, PATCH, PUT, DELETE) are blocked.
    Set via TOCONLINE_READ_ONLY=true environment variable or in .env file."""

    max_write_calls_per_session: int = 50
    """Maximum number of write tool calls allowed per MCP session.
    Prevents runaway LLM loops from making unbounded destructive API calls.
    Set to 0 to disable the limit. Default: 50."""

    modules: list[str] | None = None
    """Comma-separated list of tool module names to load.
    When unset (default), all 11 modules are loaded.
    Example: TOCONLINE_MODULES=auxiliary,customers,sales_documents
    Available: customers, suppliers, addresses, contacts, products, services,
               sales_documents, sales_receipts, purchase_documents,
               purchase_payments, auxiliary"""

    @field_validator("modules", mode="before")
    @classmethod
    def _parse_modules(cls, v: object) -> list[str] | None:
        """Accept a comma-separated string from the environment."""
        if v is None or v == "":
            return None
        if isinstance(v, str):
            return [m.strip() for m in v.split(",") if m.strip()]
        return v  # already a list (e.g. from direct instantiation in tests)


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return the cached settings instance."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
