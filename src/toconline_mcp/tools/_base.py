"""Shared helpers for TOC Online tool modules.

Centralises the repeated boilerplate that was duplicated across all 11 tool
files:
  - ``get_client``  — extract the shared API client from the MCP lifespan context
  - Re-exports of ``ToolError`` and ``TOCOnlineError`` so each tool file only
    needs a single internal import instead of two external ones.
"""

from __future__ import annotations

import re

from mcp.server.fastmcp import Context
from mcp.server.fastmcp.exceptions import ToolError  # noqa: F401 — re-exported

from toconline_mcp.client import (
    TOCOnlineClient,
    TOCOnlineError,
)  # noqa: F401 — re-exported

__all__ = ["get_client", "validate_resource_id", "ToolError", "TOCOnlineError"]

# Resource IDs from TOC Online are always positive integers.
_RESOURCE_ID_RE = re.compile(r"^\d{1,20}$")


def validate_resource_id(value: str, name: str = "id") -> str:
    """Validate that *value* looks like a safe numeric resource ID.

    Raises ToolError if the value contains non-numeric characters, preventing
    path-traversal or injection via crafted ID strings.
    """
    if not _RESOURCE_ID_RE.match(value):
        raise ToolError(f"Invalid {name}: expected a numeric ID, got {value!r}.")
    return value


def get_client(ctx: Context) -> TOCOnlineClient:
    """Extract the shared API client from the MCP lifespan context."""
    return ctx.request_context.lifespan_context["api_client"]
