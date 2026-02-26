"""MCP tools for managing TOC Online Addresses.

Endpoints covered:
  GET    /api/addresses/{id}      -> get_address
  POST   /api/addresses           -> create_address
  PATCH  /api/addresses           -> update_address  (id embedded in payload)
  DELETE /api/addresses/{id}      -> delete_address

Addresses are linked to a Customer or Supplier via ``addressable_type`` and
``addressable_id``.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from toconline_mcp.app import mcp, write_tool
from toconline_mcp.tools._base import (
    get_client,
    validate_resource_id,
    ToolError,
    TOCOnlineError,
)

# ---------------------------------------------------------------------------
# Input / Output models
# ---------------------------------------------------------------------------


class AddressAttributes(BaseModel):
    """Attributes for creating a new address."""

    address_detail: Annotated[
        str,
        Field(description="Street address line (e.g. 'Av. da Liberdade, 10')."),
    ]
    addressable_id: Annotated[
        int,
        Field(
            description="Numeric ID of the Customer or Supplier this address belongs to."
        ),
    ]
    addressable_type: Annotated[
        Literal["Customer", "Supplier"],
        Field(
            description="Whether this address belongs to a 'Customer' or 'Supplier'."
        ),
    ]
    city: Annotated[
        str | None,
        Field(default=None, description="City name."),
    ] = None
    postcode: Annotated[
        str | None,
        Field(default=None, description="Postal code (e.g. '1000-101')."),
    ] = None
    region: Annotated[
        str | None,
        Field(default=None, description="Region / district name."),
    ] = None
    # NOTE: name, is_primary, and country_id are not listed in the spec's POST
    # request body schema (only address_detail, addressable_id, addressable_type,
    # city, postcode, region are documented). They are accepted by the server
    # at create time but may be silently ignored for some fields.
    name: Annotated[
        str | None,
        Field(
            default=None, description="Address label / name (e.g. 'Sede', 'Warehouse')."
        ),
    ] = None
    is_primary: Annotated[
        bool | None,
        Field(
            default=None, description="Whether this is the entity's primary address."
        ),
    ] = None
    country_id: Annotated[
        str | None,
        Field(default=None, description="Country ID from /api/countries."),
    ] = None


class AddressUpdateAttributes(BaseModel):
    """Attributes that can be updated on an existing address (all optional)."""

    address_detail: Annotated[
        str | None,
        Field(
            default=None,
            description="Street address line (e.g. 'Av. da Liberdade, 10').",
        ),
    ] = None
    city: Annotated[
        str | None,
        Field(default=None, description="City name."),
    ] = None
    country_id: Annotated[
        str | None,
        Field(default=None, description="Country ID from /api/countries."),
    ] = None
    name: Annotated[
        str | None,
        Field(
            default=None, description="Address label / name (e.g. 'Sede', 'Warehouse')."
        ),
    ] = None
    postcode: Annotated[
        str | None,
        Field(default=None, description="Postal code (e.g. '1000-101')."),
    ] = None
    region: Annotated[
        str | None,
        Field(default=None, description="Region / district name."),
    ] = None


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def get_address(
    ctx: Context,
    address_id: Annotated[str, Field(description="The TOC Online address ID.")],
) -> dict[str, Any]:
    """Return a single address by ID, including all associated attributes."""
    client = get_client(ctx)
    validate_resource_id(address_id, "address_id")
    try:
        response = await client.get(f"/api/addresses/{address_id}")
    except TOCOnlineError as exc:
        await ctx.error(f"get_address({address_id}) failed: {exc}")
        raise ToolError(str(exc))

    item = response.get("data", {})
    return {"id": item.get("id"), **item.get("attributes", {})}


@write_tool
async def create_address(
    ctx: Context,
    attributes: Annotated[
        AddressAttributes,
        Field(description="Address data to create, linked to a Customer or Supplier."),
    ],
) -> dict[str, Any]:
    """Create a new address and link it to a Customer or Supplier.

    Returns the newly created address record including its assigned ID.
    """
    client = get_client(ctx)
    payload = {
        "data": {
            "type": "addresses",
            "attributes": attributes.model_dump(exclude_none=True),
        }
    }
    try:
        response = await client.post("/api/addresses", json=payload)
    except TOCOnlineError as exc:
        await ctx.error(f"create_address failed: {exc}")
        raise ToolError(str(exc))

    item = response.get("data", {})
    await ctx.info(f"Address created with id={item.get('id')}")
    return {"id": item.get("id"), **item.get("attributes", {})}


@write_tool
async def update_address(
    ctx: Context,
    address_id: Annotated[
        str, Field(description="The TOC Online address ID to update.")
    ],
    attributes: Annotated[
        AddressUpdateAttributes,
        Field(description="Fields to update (only provided fields are changed)."),
    ],
) -> dict[str, Any]:
    """Update an existing address's attributes.

    Only supply the fields you want to change; omitted fields remain unchanged.
    """
    client = get_client(ctx)
    validate_resource_id(address_id, "address_id")
    payload = {
        "data": {
            "type": "addresses",
            "id": address_id,
            "attributes": attributes.model_dump(exclude_none=True),
        }
    }
    try:
        response = await client.patch("/api/addresses", json=payload)
    except TOCOnlineError as exc:
        await ctx.error(f"update_address({address_id}) failed: {exc}")
        raise ToolError(str(exc))

    item = response.get("data", {})
    await ctx.info(f"Address {address_id} updated")
    return {"id": item.get("id"), **item.get("attributes", {})}


@write_tool
async def delete_address(
    ctx: Context,
    address_id: Annotated[
        str, Field(description="The TOC Online address ID to delete.")
    ],
) -> dict[str, Any]:
    """Delete an address by ID.

    Returns a confirmation meta object on success.
    """
    client = get_client(ctx)
    validate_resource_id(address_id, "address_id")
    try:
        response = await client.delete(f"/api/addresses/{address_id}")
    except TOCOnlineError as exc:
        await ctx.error(f"delete_address({address_id}) failed: {exc}")
        raise ToolError(str(exc))

    await ctx.info(f"Address {address_id} deleted")
    return response.get("meta", {"result": "deleted"})
