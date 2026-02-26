"""Secure token storage using the OS keychain.

Uses the ``keyring`` library to store and retrieve the OAuth2 refresh token
in the system's credential manager (macOS Keychain, GNOME Keyring,
Windows Credential Manager, etc.).

This avoids storing secrets in plain text ``.env`` files.  The ``.env``
``TOCONLINE_REFRESH_TOKEN`` is kept as a fallback for headless / CI / Docker
environments where no keychain backend is available.

Service and account names are namespaced to this application so they don't
collide with other software.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_SERVICE_NAME = "toconline-mcp"
_REFRESH_TOKEN_KEY = "refresh_token"


def store_refresh_token(token: str) -> bool:
    """Persist *token* in the OS keychain.

    Returns True on success, False if the keychain backend is unavailable.
    """
    try:
        import keyring
        from keyring.errors import NoKeyringError
    except ImportError:
        logger.debug("keyring package not installed — cannot store refresh token.")
        return False

    try:
        keyring.set_password(_SERVICE_NAME, _REFRESH_TOKEN_KEY, token)
        return True
    except NoKeyringError:
        logger.debug("Keychain backend unavailable — cannot store refresh token.")
        return False
    except Exception:
        logger.warning("Failed to store refresh token in keychain.", exc_info=True)
        return False


def load_refresh_token() -> str | None:
    """Load the refresh token from the OS keychain.

    Returns the token string, or None if not found or keychain unavailable.
    """
    try:
        import keyring
        from keyring.errors import NoKeyringError
    except ImportError:
        logger.debug("keyring package not installed — cannot load refresh token.")
        return None

    try:
        token = keyring.get_password(_SERVICE_NAME, _REFRESH_TOKEN_KEY)
        return token if token else None
    except NoKeyringError:
        logger.debug("Keychain backend unavailable — cannot load refresh token.")
        return None
    except Exception:
        logger.warning("Failed to load refresh token from keychain.", exc_info=True)
        return None


def delete_refresh_token() -> bool:
    """Remove the refresh token from the OS keychain.

    Returns True on success (or if the key didn't exist), False on error.
    """
    try:
        import keyring
        from keyring.errors import NoKeyringError, PasswordDeleteError
    except ImportError:
        logger.debug("keyring package not installed — nothing to delete.")
        return False

    try:
        keyring.delete_password(_SERVICE_NAME, _REFRESH_TOKEN_KEY)
        return True
    except PasswordDeleteError:
        return True  # Already gone — that's fine.
    except NoKeyringError:
        logger.debug("Keychain backend unavailable — nothing to delete.")
        return False
    except Exception:
        logger.warning("Failed to delete refresh token from keychain.", exc_info=True)
        return False


def has_refresh_token() -> bool:
    """Return True if a refresh token exists in the OS keychain."""
    return load_refresh_token() is not None
