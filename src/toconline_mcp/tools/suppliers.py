"""MCP tools for managing TOC Online Suppliers.

Endpoints covered:
  GET    /api/suppliers           -> list_suppliers
  GET    /api/suppliers/{id}      -> get_supplier
  POST   /api/suppliers           -> create_supplier
  PATCH  /api/suppliers           -> update_supplier
  DELETE /api/suppliers/{id}      -> delete_supplier
"""

from __future__ import annotations

from typing import Annotated, Any

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


class SupplierAttributes(BaseModel):
    """Attributes for creating a new supplier."""

    business_name: Annotated[str, Field(description="Company or individual name.")]
    tax_registration_number: Annotated[
        str,
        Field(
            description="NIF (Portuguese tax identification number) or foreign equivalent."
        ),
    ]
    country_iso_alpha_2: Annotated[
        str | None,
        Field(
            default=None,
            description="ISO 3166-1 alpha-2 country code (e.g. 'PT', 'US').",
        ),
    ] = None
    tax_country_region: Annotated[
        str | None,
        Field(
            default=None,
            description="Tax country region code (e.g. 'PT', 'PT-AC', 'NON-UE').",
        ),
    ] = None
    website: Annotated[
        str | None,
        Field(default=None, description="Supplier website URL."),
    ] = None
    internal_observations: Annotated[
        str | None,
        Field(default=None, description="Internal (private) observations."),
    ] = None
    is_independent_worker: Annotated[
        bool | None,
        Field(
            default=None,
            description="True if the supplier is a sole trader / independent worker.",
        ),
    ] = None
    is_tax_exempt: Annotated[
        bool | None,
        Field(default=None, description="Whether the supplier is tax exempt."),
    ] = None
    is_taxable: Annotated[
        bool | None,
        Field(default=None, description="Whether the supplier is subject to taxation."),
    ] = None
    self_billing: Annotated[
        bool | None,
        Field(default=None, description="Whether self-billing applies."),
    ] = None
    trusted_email_source: Annotated[
        bool | None,
        Field(
            default=None, description="Whether emails from this supplier are trusted."
        ),
    ] = None
    tax_exemption_reason_id: Annotated[
        str | None,
        Field(
            default=None, description="ID of the tax exemption reason, if applicable."
        ),
    ] = None
    document_series_id: Annotated[
        str | None,
        Field(
            default=None, description="Default document series ID for this supplier."
        ),
    ] = None
    accounting_number: Annotated[
        str | None,
        Field(default=None, description="Accounting number for this supplier."),
    ] = None
    saft_import_id: Annotated[
        str | None,
        Field(
            default=None,
            description="SAF-T import ID, if the supplier was imported via SAF-T.",
        ),
    ] = None


class SupplierUpdateAttributes(BaseModel):
    """Attributes that can be updated on an existing supplier (all optional)."""

    business_name: str | None = None
    tax_registration_number: str | None = None
    country_iso_alpha_2: str | None = None
    tax_country_region: str | None = None
    website: str | None = None
    internal_observations: str | None = None
    is_independent_worker: bool | None = None
    is_tax_exempt: bool | None = None
    is_taxable: bool | None = None
    self_billing: bool | None = None
    trusted_email_source: bool | None = None
    tax_exemption_reason_id: str | None = None
    document_series_id: str | None = None
    accounting_number: str | None = None
    saft_import_id: str | None = None


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_suppliers(
    ctx: Context,
    business_name: Annotated[
        str | None,
        Field(
            default=None,
            description="Filter by supplier name (partial match). Maps to filter[business_name].",
        ),
    ] = None,
    tax_registration_number: Annotated[
        str | None,
        Field(
            default=None,
            description="Filter by NIF / tax number (exact match). Maps to filter[tax_registration_number].",
        ),
    ] = None,
    page: Annotated[
        int | None,
        Field(
            default=None, description="Page number (1-based). Omit for the first page."
        ),
    ] = None,
    per_page: Annotated[
        int | None,
        Field(
            default=None,
            description="Items per page (API default when omitted; typically 25 max).",
        ),
    ] = None,
) -> dict[str, Any]:
    """Return suppliers for the current company.

    Optionally filter by ``business_name`` (partial match) or
    ``tax_registration_number`` (exact NIF) to narrow results before paginating.
    Each item contains the supplier id and its attributes (name, NIF, country, etc.).
    """
    client = get_client(ctx)
    params: dict[str, str] = {}
    if business_name:
        params["filter[business_name]"] = business_name
    if tax_registration_number:
        params["filter[tax_registration_number]"] = tax_registration_number
    if page is not None:
        params["page[number]"] = str(page)
    if per_page is not None:
        params["page[size]"] = str(per_page)
    try:
        response = await client.get("/api/suppliers", params=params)
    except TOCOnlineError as exc:
        await ctx.error(f"list_suppliers failed: {exc}")
        raise ToolError(str(exc))

    data = response.get("data", [])
    if not isinstance(data, list):
        data = [data]

    items = [{"id": item.get("id"), **item.get("attributes", {})} for item in data]
    meta = response.get("meta", {})
    return {"data": items, "meta": meta}


@mcp.tool()
async def get_supplier(
    ctx: Context,
    supplier_id: Annotated[str, Field(description="The TOC Online supplier ID.")],
) -> dict[str, Any]:
    """Return a single supplier by ID, including their addresses, contacts, and bank accounts."""
    client = get_client(ctx)
    validate_resource_id(supplier_id, "supplier_id")
    try:
        response = await client.get(f"/api/suppliers/{supplier_id}")
    except TOCOnlineError as exc:
        await ctx.error(f"get_supplier({supplier_id}) failed: {exc}")
        raise ToolError(str(exc))

    item = response.get("data", {})
    return {"id": item.get("id"), **item.get("attributes", {})}


@write_tool
async def create_supplier(
    ctx: Context,
    attributes: Annotated[
        SupplierAttributes, Field(description="Supplier data to create.")
    ],
) -> dict[str, Any]:
    """Create a new supplier.

    Returns the newly created supplier record including its assigned ID.
    Raises an error if the NIF is invalid or already exists.
    """
    client = get_client(ctx)
    payload = {
        "data": {
            "type": "suppliers",
            "attributes": attributes.model_dump(exclude_none=True),
        }
    }
    try:
        response = await client.post("/api/suppliers", json=payload)
    except TOCOnlineError as exc:
        await ctx.error(f"create_supplier failed: {exc}")
        raise ToolError(str(exc))

    item = response.get("data", {})
    await ctx.info(f"Supplier created with id={item.get('id')}")
    return {"id": item.get("id"), **item.get("attributes", {})}


@write_tool
async def update_supplier(
    ctx: Context,
    supplier_id: Annotated[
        str, Field(description="The TOC Online supplier ID to update.")
    ],
    attributes: Annotated[
        SupplierUpdateAttributes,
        Field(description="Fields to update (only provided fields are changed)."),
    ],
) -> dict[str, Any]:
    """Update an existing supplier's attributes.

    Only supply the fields you want to change; omitted fields remain unchanged.
    """
    client = get_client(ctx)
    validate_resource_id(supplier_id, "supplier_id")
    payload = {
        "data": {
            "type": "suppliers",
            "id": supplier_id,
            "attributes": attributes.model_dump(exclude_none=True),
        }
    }
    try:
        response = await client.patch("/api/suppliers", json=payload)
    except TOCOnlineError as exc:
        await ctx.error(f"update_supplier({supplier_id}) failed: {exc}")
        raise ToolError(str(exc))

    item = response.get("data", {})
    await ctx.info(f"Supplier {supplier_id} updated")
    return {"id": item.get("id"), **item.get("attributes", {})}


@write_tool
async def delete_supplier(
    ctx: Context,
    supplier_id: Annotated[
        str, Field(description="The TOC Online supplier ID to delete.")
    ],
) -> dict[str, Any]:
    """Delete a supplier by ID.

    Returns a confirmation meta object on success.
    Raises an error if the supplier has issued documents or payments and cannot be deleted.
    """
    client = get_client(ctx)
    validate_resource_id(supplier_id, "supplier_id")
    try:
        response = await client.delete(f"/api/suppliers/{supplier_id}")
    except TOCOnlineError as exc:
        await ctx.error(f"delete_supplier({supplier_id}) failed: {exc}")
        raise ToolError(str(exc))

    await ctx.info(f"Supplier {supplier_id} deleted")
    return response.get("meta", {"result": "deleted"})
