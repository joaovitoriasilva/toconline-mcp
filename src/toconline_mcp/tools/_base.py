"""Shared helpers for TOC Online tool modules.

Centralises the repeated boilerplate that was duplicated across all 11 tool
files:
  - ``get_client``  — extract the shared API client from the MCP lifespan context
  - Re-exports of ``ToolError`` and ``TOCOnlineError`` so each tool file only
    needs a single internal import instead of two external ones.
  - ``flatten_items`` / ``response_meta`` — read records out of either a JSON:API
    envelope or a bare ``/api/v1/`` response.
"""

from __future__ import annotations

import re
from typing import Any

from mcp.server.fastmcp import Context
from mcp.server.fastmcp.exceptions import ToolError

from toconline_mcp.client import (
    TOCOnlineClient,
    TOCOnlineError,
)

__all__ = [
    "TOCOnlineError",
    "ToolError",
    "flatten_items",
    "get_client",
    "response_meta",
    "validate_resource_id",
]

# Top-level keys a JSON:API document may carry. A dict made only of these is an
# envelope; anything else is a bare record (v1 records can have their own
# "data" field, so the presence of "data" alone proves nothing).
_JSONAPI_TOP_LEVEL_KEYS = {"data", "meta", "links", "included", "jsonapi", "errors"}


def _is_jsonapi_envelope(response: Any) -> bool:
    return (
        isinstance(response, dict)
        and "data" in response
        and set(response) <= _JSONAPI_TOP_LEVEL_KEYS
    )


def flatten_items(response: Any) -> list[dict[str, Any]]:
    """Return the records in *response* as flat ``{id, **fields}`` dicts.

    JSON:API endpoints (``/api/...``) wrap records as
    ``{"data": [{"id", "attributes"}]}``. The ``/api/v1/...`` endpoints return a
    bare JSON array for lists and a bare object for a single record, with the
    fields at the top level. Both shapes are accepted.
    """
    data = response["data"] if _is_jsonapi_envelope(response) else response
    if not isinstance(data, list):
        data = [data]
    items = []
    for item in data:
        if not isinstance(item, dict):
            continue
        attributes = item.get("attributes")
        if isinstance(attributes, dict):
            items.append({"id": item.get("id"), **attributes})
        else:
            items.append(item)
    return items


def response_meta(response: Any) -> dict[str, Any]:
    """Return the JSON:API ``meta`` block, or ``{}`` for bare v1 responses."""
    if _is_jsonapi_envelope(response):
        return response.get("meta", {})
    return {}


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
