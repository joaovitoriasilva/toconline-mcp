"""MCP tools for managing TOC Online Contacts (email contacts).

Endpoints covered per the official API spec:
  GET    /api/contacts            -> list_contacts
  GET    /api/contacts/{id}       -> get_contact
  POST   /api/contacts            -> create_contact
  PATCH  /api/contacts            -> update_contact  (ID goes in request body)

Note: DELETE for contacts is not documented in the official API spec.
``delete_contact`` is included as a best-effort attempt using the standard
pattern; it may or may not be supported by the server.

Contacts represent email/phone details.  To link a contact to a Supplier or
Customer use ``contactable_id`` (the entity's numeric ID) and
``contactable_type`` ("Supplier" or "Customer") on create.  These fields go
directly in the attributes payload, **not** in JSON:API relationships.
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

from toconline_mcp.app import mcp, write_tool
from toconline_mcp.tools._base import (
    TOCOnlineError,
    ToolError,
    get_client,
    validate_resource_id,
)

# ---------------------------------------------------------------------------
# Input / Output models
# ---------------------------------------------------------------------------


class ContactAttributes(BaseModel):
    """Attributes for creating a new contact."""

    email: Annotated[
        str,
        Field(description="Email address for this contact."),
    ]
    contactable_id: Annotated[
        int,
        Field(
            description=(
                "Numeric ID of the entity (Customer or Supplier) to link this "
                "contact to."
            )
        ),
    ]
    contactable_type: Annotated[
        str,
        Field(
            description=('Type of the linked entity. Must be "Customer" or "Supplier".')
        ),
    ]
    is_primary: Annotated[
        bool | None,
        Field(
            default=None,
            description="Whether this is the primary contact for the entity.",
        ),
    ] = None
    name: Annotated[
        str | None,
        Field(default=None, description="Contact person's name."),
    ] = None
    mobile_number: Annotated[
        str | None,
        Field(default=None, description="Mobile phone number."),
    ] = None
    phone_number: Annotated[
        str | None,
        Field(default=None, description="Landline phone number."),
    ] = None
    position: Annotated[
        str | None,
        Field(default=None, description="Job title or position of the contact person."),
    ] = None
    categories: Annotated[
        list[str] | None,
        Field(
            default=None,
            description=('Optional category tags for the contact, e.g. ["general"].'),
        ),
    ] = None


class ContactUpdateAttributes(BaseModel):
    """Attributes that can be updated on an existing contact (all optional)."""

    email: str | None = None
    name: str | None = None
    is_primary: bool | None = None
    mobile_number: str | None = None
    phone_number: str | None = None
    position: str | None = None


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_contacts(ctx: Context) -> list[dict[str, Any]]:
    """Return all contacts registered in the account."""
    client = get_client(ctx)
    try:
        response = await client.get("/api/contacts")
    except TOCOnlineError as exc:
        await ctx.error(f"list_contacts failed: {exc}")
        raise ToolError(str(exc)) from exc

    items = response.get("data", [])
    return [{"id": item.get("id"), **item.get("attributes", {})} for item in items]


@mcp.tool()
async def get_contact(
    ctx: Context,
    contact_id: Annotated[str, Field(description="The TOC Online contact ID.")],
) -> dict[str, Any]:
    """Return a single contact by ID, including email, name, and phone details."""
    client = get_client(ctx)
    validate_resource_id(contact_id, "contact_id")
    try:
        response = await client.get(f"/api/contacts/{contact_id}")
    except TOCOnlineError as exc:
        await ctx.error(f"get_contact({contact_id}) failed: {exc}")
        raise ToolError(str(exc)) from exc

    item = response.get("data", {})
    return {"id": item.get("id"), **item.get("attributes", {})}


@write_tool
async def create_contact(
    ctx: Context,
    attributes: Annotated[
        ContactAttributes,
        Field(description="Contact data to create, linked to a Customer or Supplier."),
    ],
) -> dict[str, Any]:
    """Create a new email/phone contact linked to a Customer or Supplier.

    Pass ``contactable_id`` (the entity's numeric ID) and ``contactable_type``
    ("Customer" or "Supplier") together with the required ``email``.
    Returns the newly created contact record including its assigned ID.
    """
    client = get_client(ctx)
    attrs = attributes.model_dump(exclude_none=True)
    payload = {
        "data": {
            "type": "contacts",
            "attributes": attrs,
        }
    }
    try:
        response = await client.post("/api/contacts", json=payload)
    except TOCOnlineError as exc:
        await ctx.error(f"create_contact failed: {exc}")
        raise ToolError(str(exc)) from exc

    item = response.get("data", {})
    await ctx.info(f"Contact created with id={item.get('id')}")
    return {"id": item.get("id"), **item.get("attributes", {})}


@write_tool
async def update_contact(
    ctx: Context,
    contact_id: Annotated[
        str, Field(description="The TOC Online contact ID to update.")
    ],
    attributes: Annotated[
        ContactUpdateAttributes,
        Field(description="Fields to update (only provided fields are changed)."),
    ],
) -> dict[str, Any]:
    """Update an existing contact's attributes.

    Only supply the fields you want to change; omitted fields remain unchanged.
    """
    client = get_client(ctx)
    validate_resource_id(contact_id, "contact_id")
    payload = {
        "data": {
            "type": "contacts",
            "id": contact_id,
            "attributes": attributes.model_dump(exclude_none=True),
        }
    }
    try:
        response = await client.patch("/api/contacts", json=payload)
    except TOCOnlineError as exc:
        await ctx.error(f"update_contact({contact_id}) failed: {exc}")
        raise ToolError(str(exc)) from exc

    item = response.get("data", {})
    await ctx.info(f"Contact {contact_id} updated")
    return {"id": item.get("id"), **item.get("attributes", {})}


@write_tool
async def delete_contact(
    ctx: Context,
    contact_id: Annotated[
        str, Field(description="The TOC Online contact ID to delete.")
    ],
) -> dict[str, Any]:
    """Delete a contact by ID.

    Returns a confirmation meta object on success.
    """
    client = get_client(ctx)
    validate_resource_id(contact_id, "contact_id")
    try:
        response = await client.delete(f"/api/contacts/{contact_id}")
    except TOCOnlineError as exc:
        await ctx.error(f"delete_contact({contact_id}) failed: {exc}")
        raise ToolError(str(exc)) from exc

    await ctx.info(f"Contact {contact_id} deleted")
    return response.get("meta", {"result": "deleted"})
