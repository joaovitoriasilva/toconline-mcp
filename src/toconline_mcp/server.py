"""TOC Online MCP server entry point.

Run locally:
    uv run toconline-mcp

Install to Claude Desktop:
    uv run mcp install src/toconline_mcp/server.py

Inspect with MCP Inspector:
    uv run mcp dev src/toconline_mcp/server.py

Module filtering:
    Set TOCONLINE_MODULES=auxiliary,customers,sales_documents to load only
    specific tool modules.  When unset, all 11 modules are loaded.
"""

from __future__ import annotations

import importlib

from toconline_mcp.app import mcp
from toconline_mcp.settings import get_settings

# All available tool module short-names (suffix of `toconline_mcp.tools.*`).
_ALL_MODULES: list[str] = [
    "customers",
    "suppliers",
    "addresses",
    "contacts",
    "products",
    "services",
    "sales_documents",
    "sales_receipts",
    "purchase_documents",
    "purchase_payments",
    "auxiliary",
]


def _load_tool_modules() -> None:
    """Import tool modules so their @mcp.tool() decorators register.

    Respects the TOCONLINE_MODULES setting: when set, only the listed modules
    are imported; when unset, all modules are imported.
    """
    settings = get_settings()
    requested = settings.modules  # None → load all

    if requested is not None:
        unknown = set(requested) - set(_ALL_MODULES)
        if unknown:
            raise ValueError(
                f"Unknown module(s) in TOCONLINE_MODULES: {', '.join(sorted(unknown))}. "
                f"Valid names: {', '.join(_ALL_MODULES)}"
            )
        modules_to_load = requested
    else:
        modules_to_load = _ALL_MODULES

    for name in modules_to_load:
        importlib.import_module(f"toconline_mcp.tools.{name}")


# Tool modules must be imported before mcp.run() so their @mcp.tool()
# decorators register against the shared FastMCP instance in app.py.
_load_tool_modules()


def main() -> None:
    """Run the MCP server over stdio (default transport for Claude Desktop)."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
