"""MCP tools for managing TOC Online Customers.

Endpoints covered:
  GET    /api/customers           -> list_customers
  GET    /api/customers/{id}      -> get_customer
  POST   /api/customers           -> create_customer
  PATCH  /api/customers           -> update_customer
  DELETE /api/customers/{id}      -> delete_customer
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


class CustomerAttributes(BaseModel):
    """Attributes for creating or updating a customer.

    Note: The fields ``country_iso_alpha_2``, ``tax_country_region``,
    ``is_tax_exempt``, ``not_final_customer``, and ``cashed_vat`` are not
    listed in the POST /api/customers request body schema in the OpenAPI spec,
    but they are documented for PATCH, returned in POST responses, and are
    accepted by the API when provided on creation. They are kept here as
    optional fields.
    """

    business_name: Annotated[str, Field(description="Company or individual name.")]
    tax_registration_number: Annotated[
        str,
        Field(
            description="NIF (Portuguese tax identification number) or foreign"
            " equivalent."
        ),
    ]
    contact_name: Annotated[
        str | None,
        Field(default=None, description="Primary contact person name."),
    ] = None
    email: Annotated[
        str | None,
        Field(default=None, description="Customer email address."),
    ] = None
    # Note: spec shows POST body as number, PATCH body as string —
    # str | int covers both.
    phone_number: Annotated[
        str | int | None,
        Field(default=None, description="Landline phone number."),
    ] = None
    mobile_number: Annotated[
        str | int | None,
        Field(default=None, description="Mobile phone number."),
    ] = None
    website: Annotated[
        str | None,
        Field(default=None, description="Customer website URL."),
    ] = None
    observations: Annotated[
        str | None,
        Field(default=None, description="Public observations visible on documents."),
    ] = None
    internal_observations: Annotated[
        str | None,
        Field(default=None, description="Internal (private) observations."),
    ] = None
    # The following five fields are not in the POST spec request body but are
    # accepted by the API and returned in the response.
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
    is_tax_exempt: Annotated[
        bool | None,
        Field(default=None, description="Whether the customer is tax exempt."),
    ] = None
    not_final_customer: Annotated[
        bool | None,
        Field(
            default=None,
            description="True if the customer is a business (B2B), not a final"
            " consumer.",
        ),
    ] = None
    cashed_vat: Annotated[
        bool | None,
        Field(
            default=None,
            description="Whether cashed VAT regime applies to this customer.",
        ),
    ] = None


class CustomerUpdateAttributes(BaseModel):
    """Attributes that can be updated on an existing customer (all optional)."""

    business_name: str | None = None
    tax_registration_number: str | None = None
    contact_name: str | None = None
    email: str | None = None
    phone_number: str | int | None = None
    mobile_number: str | int | None = None
    website: str | None = None
    observations: str | None = None
    internal_observations: str | None = None
    country_iso_alpha_2: str | None = None
    tax_country_region: str | None = None
    is_tax_exempt: bool | None = None
    not_final_customer: bool | None = None
    cashed_vat: bool | None = None


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_customers(
    ctx: Context,
    business_name: Annotated[
        str | None,
        Field(
            default=None,
            description="Filter by customer name (partial match). Maps to"
            " filter[business_name].",
        ),
    ] = None,
    tax_registration_number: Annotated[
        str | None,
        Field(
            default=None,
            description="Filter by NIF / tax number (exact match). Maps to"
            " filter[tax_registration_number].",
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
    """Return customers for the current company.

    Optionally filter by ``business_name`` (partial match) or
    ``tax_registration_number`` (exact NIF) to narrow results before paginating.
    Each item contains the customer id and its attributes (name, NIF, email, etc.).
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
        response = await client.get("/api/customers", params=params)
    except TOCOnlineError as exc:
        await ctx.error(f"list_customers failed: {exc}")
        raise ToolError(str(exc)) from exc

    data = response.get("data", [])
    if not isinstance(data, list):
        data = [data]

    items = [{"id": item.get("id"), **item.get("attributes", {})} for item in data]
    meta = response.get("meta", {})
    return {"data": items, "meta": meta}


@mcp.tool()
async def get_customer(
    ctx: Context,
    customer_id: Annotated[str, Field(description="The TOC Online customer ID.")],
) -> dict[str, Any]:
    """Return a single customer by ID, including their addresses and email addresses."""
    client = get_client(ctx)
    validate_resource_id(customer_id, "customer_id")
    try:
        response = await client.get(f"/api/customers/{customer_id}")
    except TOCOnlineError as exc:
        await ctx.error(f"get_customer({customer_id}) failed: {exc}")
        raise ToolError(str(exc)) from exc

    item = response.get("data", {})
    return {"id": item.get("id"), **item.get("attributes", {})}


@write_tool
async def create_customer(
    ctx: Context,
    attributes: Annotated[
        CustomerAttributes, Field(description="Customer data to create.")
    ],
) -> dict[str, Any]:
    """Create a new customer.

    Returns the newly created customer record including its assigned ID.
    Raises a 400 error if the NIF is invalid, or a 403 error if a customer
    with the same NIF already exists.
    """
    client = get_client(ctx)
    payload = {
        "data": {
            "type": "customers",
            "attributes": attributes.model_dump(exclude_none=True),
        }
    }
    try:
        response = await client.post("/api/customers", json=payload)
    except TOCOnlineError as exc:
        await ctx.error(f"create_customer failed: {exc}")
        raise ToolError(str(exc)) from exc

    item = response.get("data", {})
    await ctx.info(f"Customer created with id={item.get('id')}")
    return {"id": item.get("id"), **item.get("attributes", {})}


@write_tool
async def update_customer(
    ctx: Context,
    customer_id: Annotated[
        str, Field(description="The TOC Online customer ID to update.")
    ],
    attributes: Annotated[
        CustomerUpdateAttributes,
        Field(description="Fields to update (only provided fields are changed)."),
    ],
) -> dict[str, Any]:
    """Update an existing customer's attributes.

    Only supply the fields you want to change; omitted fields remain unchanged.
    """
    client = get_client(ctx)
    validate_resource_id(customer_id, "customer_id")
    payload = {
        "data": {
            "type": "customers",
            "id": customer_id,
            "attributes": attributes.model_dump(exclude_none=True),
        }
    }
    try:
        response = await client.patch("/api/customers", json=payload)
    except TOCOnlineError as exc:
        await ctx.error(f"update_customer({customer_id}) failed: {exc}")
        raise ToolError(str(exc)) from exc

    item = response.get("data", {})
    await ctx.info(f"Customer {customer_id} updated")
    return {"id": item.get("id"), **item.get("attributes", {})}


@write_tool
async def delete_customer(
    ctx: Context,
    customer_id: Annotated[
        str, Field(description="The TOC Online customer ID to delete.")
    ],
) -> dict[str, Any]:
    """Delete a customer by ID.

    Returns a confirmation meta object on success.
    Raises an error if the customer has associated documents or cannot be deleted.
    """
    client = get_client(ctx)
    validate_resource_id(customer_id, "customer_id")
    try:
        response = await client.delete(f"/api/customers/{customer_id}")
    except TOCOnlineError as exc:
        await ctx.error(f"delete_customer({customer_id}) failed: {exc}")
        raise ToolError(str(exc)) from exc

    await ctx.info(f"Customer {customer_id} deleted")
    return response.get("meta", {"result": "deleted"})
