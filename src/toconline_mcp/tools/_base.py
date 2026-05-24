"""Shared helpers for TOC Online tool modules.

Centralises the repeated boilerplate that was duplicated across all 11 tool
files:
  - ``get_client``  — extract the shared API client from the MCP lifespan context
  - ``unwrap_list`` / ``unwrap_item`` — normalize the inconsistent JSON shapes
    returned by TOC Online's v1 endpoints (bare list, bare object, or proper
    JSON:API ``{data, meta}`` envelope).
  - Re-exports of ``ToolError`` and ``TOCOnlineError`` so each tool file only
    needs a single internal import instead of two external ones.
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
    "get_client",
    "unwrap_item",
    "unwrap_list",
    "validate_resource_id",
]

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


def _flatten_item(item: dict[str, Any]) -> dict[str, Any]:
    """Flatten a JSON:API resource ``{id, type, attributes}`` to ``{id, ...attrs}``.

    Returns the item as-is if it already looks flat (no ``attributes`` key).
    """
    if "attributes" in item and isinstance(item.get("attributes"), dict):
        return {"id": item.get("id"), **item["attributes"]}
    return item


def unwrap_list(response: Any) -> dict[str, Any]:
    """Normalize a list response to ``{"data": [...], "meta": {...}}``.

    TOC Online's v1 list endpoints return inconsistent shapes:
      - Bare list at the JSON root:  ``[{...}, {...}]``
      - JSON:API envelope:           ``{"data": [{...}], "meta": {...}}``
      - Single object:               ``{...}`` (degenerate single-item list)

    Each item is flattened to ``{id, ...attrs}`` regardless of whether it
    arrived in JSON:API ``{id, type, attributes}`` form or already flat.
    """
    if isinstance(response, list):
        data: Any = response
        meta: dict[str, Any] = {}
    elif isinstance(response, dict):
        data = response.get("data", [])
        if not isinstance(data, list):
            data = [data]
        meta = response.get("meta", {}) or {}
    else:
        data, meta = [], {}

    items: list[dict[str, Any]] = []
    for item in data:
        if isinstance(item, dict):
            items.append(_flatten_item(item))
    return {"data": items, "meta": meta}


def unwrap_item(response: Any) -> dict[str, Any]:
    """Normalize a single-item response to a flat ``{id, ...attrs}`` dict.

    Handles all three shapes from ``unwrap_list`` plus the case where the
    server returns the resource directly at the JSON root (no envelope).
    """
    if isinstance(response, dict):
        inner = response.get("data")
        if isinstance(inner, dict):
            return _flatten_item(inner)
        if isinstance(inner, list) and inner and isinstance(inner[0], dict):
            return _flatten_item(inner[0])
        return _flatten_item(response)
    if isinstance(response, list) and response and isinstance(response[0], dict):
        return _flatten_item(response[0])
    return {}
