"""FastMCP application instance.

Defined in its own module so both server.py and tool modules can import
`mcp` without creating circular imports.

Read-only mode
--------------
Set ``TOCONLINE_READ_ONLY=true`` (or ``read_only = true`` in ``.env``) to start
the server in read-only mode.  All tools decorated with ``@write_tool`` will
still appear in the tool list so the LLM is aware of them, but every call will
return an immediate error instead of hitting the API.
"""

from __future__ import annotations

import functools
import logging
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from mcp.server.fastmcp import FastMCP

from toconline_mcp.auth import TokenStore
from toconline_mcp.client import TOCOnlineClient
from toconline_mcp.keychain import load_refresh_token
from toconline_mcp.settings import get_settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(server: FastMCP) -> AsyncIterator[dict]:
    """Initialise shared resources that tools can access via ctx.request_context.

    Token resolution priority:
      1. TOCONLINE_ACCESS_TOKEN (static, from .env) — for quick dev/testing.
      2. System keychain refresh_token — default secure path.
      3. TOCONLINE_REFRESH_TOKEN (.env fallback) — for CI/Docker/headless.
    """
    settings = get_settings()
    token_store = TokenStore()

    if settings.access_token:
        # Priority 1: static access token from env.
        token_store.load_static(settings.access_token)
    else:
        # Priority 2: keychain.
        keychain_token = load_refresh_token()
        if keychain_token:
            token_store.load_refresh_token(keychain_token)
        elif settings.refresh_token:
            # Priority 3: .env fallback.
            token_store.load_refresh_token(settings.refresh_token)

    async with TOCOnlineClient(settings, token_store) as api_client:
        yield {"api_client": api_client}


def _build_instructions() -> str:
    base = (
        "You are connected to the TOC Online accounting platform API. "
        "You can manage customers, suppliers, products, services, "
        "sales and purchase documents, receipts, payments, and auxiliary data "
        "such as taxes, countries, currencies, and document series. "
        "All monetary amounts are in EUR unless a currency is specified."
    )
    if get_settings().read_only:
        base += (
            " IMPORTANT: The server is running in READ-ONLY mode. "
            "Any tool that creates, updates, or deletes data will be rejected."
        )
    return base


mcp = FastMCP(
    name="TOC Online",
    instructions=_build_instructions(),
    lifespan=lifespan,
)


_READ_ONLY_ERROR = (
    "This server is running in read-only mode (TOCONLINE_READ_ONLY=true). "
    "Write operations (create, update, delete, finalize, send) are disabled."
)

_RATE_LIMIT_ERROR = (
    "Write operation rate limit exceeded (max {limit} per session). "
    "This safety limit prevents runaway automation. "
    "Adjust TOCONLINE_MAX_WRITE_CALLS_PER_SESSION to change the limit."
)

# Session-scoped counter for write tool invocations.
_write_call_count: int = 0


def write_tool(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator for tools that perform write operations (POST, PATCH, PUT, DELETE).

    Enforces two safety checks before executing:
      1. **Read-only mode** — rejects immediately if TOCONLINE_READ_ONLY is set.
      2. **Rate limiting** — rejects if the session has exceeded
         TOCONLINE_MAX_WRITE_CALLS_PER_SESSION (default 50, 0 = unlimited).

    In both cases the tool is still registered with FastMCP so the LLM is
    aware of its existence.

    Usage::

        @write_tool          # replaces @mcp.tool() on write operations
        async def create_customer(ctx: Context, ...) -> dict:
            ...
    """

    @mcp.tool()
    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        """Reject the call when read-only mode is active or rate limit is hit."""
        global _write_call_count
        settings = get_settings()

        if settings.read_only:
            return {"error": _READ_ONLY_ERROR}

        limit = settings.max_write_calls_per_session
        if limit > 0:
            _write_call_count += 1
            if _write_call_count > limit:
                logger.warning(
                    "Write rate limit reached (%d/%d): %s denied",
                    _write_call_count,
                    limit,
                    func.__name__,
                )
                return {"error": _RATE_LIMIT_ERROR.format(limit=limit)}

        return await func(*args, **kwargs)

    return wrapper
