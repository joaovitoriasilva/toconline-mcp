"""MCP tools for managing TOC Online Services.

Endpoints covered:
  GET    /api/services            -> list_services
  POST   /api/services            -> create_service
  PATCH  /api/services            -> update_service  (id embedded in payload)
  DELETE /api/services            -> delete_service  (id embedded in payload)
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


class ServiceAttributes(BaseModel):
    """Attributes for creating a new service."""

    item_description: Annotated[
        str,
        Field(description="Service name / description shown on documents."),
    ]
    tax_code: Annotated[
        str | None,
        Field(
            default=None,
            description="VAT tax code (e.g. 'NOR', 'INT', 'RED', 'ISE'). Optional — the API resolves it automatically from item family defaults when omitted.",
        ),
    ] = None
    sales_price: Annotated[
        float,
        Field(description="Unit sales price."),
    ]
    item_code: Annotated[
        str | None,
        Field(default=None, description="Internal service code / reference."),
    ] = None
    sales_price_includes_vat: Annotated[
        bool | None,
        Field(
            default=None, description="Whether the sales price already includes VAT."
        ),
    ] = None
    item_family_id: Annotated[
        int | None,
        Field(
            default=None, description="ID of the item family from /api/item_families."
        ),
    ] = None
    unit_of_measure_id: Annotated[
        int | None,
        Field(
            default=None,
            description="ID of the unit of measure from /api/units_of_measure.",
        ),
    ] = None
    purchase_price: Annotated[
        float | None,
        Field(default=None, description="Unit purchase / cost price."),
    ] = None
    sales_price_2: Annotated[
        float | None,
        Field(default=None, description="Secondary sales price tier."),
    ] = None
    sales_price_3: Annotated[
        float | None,
        Field(default=None, description="Tertiary sales price tier."),
    ] = None
    accounting_number: Annotated[
        str | None,
        Field(default=None, description="Accounting ledger number for this service."),
    ] = None
    notes: Annotated[
        str | None,
        Field(default=None, description="Internal notes for this service."),
    ] = None
    service_group: Annotated[
        str | None,
        Field(default=None, description="Service group identifier (e.g. 'G1')."),
    ] = None
    is_active: Annotated[
        bool | None,
        Field(
            default=None,
            description="Whether the service is active and selectable on documents.",
        ),
    ] = None
    ean_barcode: Annotated[
        str | None,
        Field(default=None, description="EAN barcode string for the service."),
    ] = None
    customs_cost: Annotated[
        float | None,
        Field(default=None, description="Customs cost."),
    ] = None
    financial_cost: Annotated[
        float | None,
        Field(default=None, description="Financial cost."),
    ] = None
    other_cost: Annotated[
        float | None,
        Field(default=None, description="Other cost."),
    ] = None
    transport_cost: Annotated[
        float | None,
        Field(default=None, description="Transport cost."),
    ] = None
    estimated_total_cost: Annotated[
        float | None,
        Field(default=None, description="Estimated total cost."),
    ] = None


class ServiceUpdateAttributes(BaseModel):
    """Attributes that can be updated on an existing service (all optional)."""

    item_description: str | None = None
    item_code: str | None = None
    tax_code: str | None = None
    sales_price: float | None = None
    sales_price_includes_vat: bool | None = None
    item_family_id: int | None = None
    unit_of_measure_id: int | None = None
    purchase_price: float | None = None
    sales_price_2: float | None = None
    sales_price_3: float | None = None
    accounting_number: str | None = None
    notes: str | None = None
    service_group: str | None = None
    is_active: bool | None = None
    ean_barcode: str | None = None
    customs_cost: float | None = None
    financial_cost: float | None = None
    other_cost: float | None = None
    transport_cost: float | None = None
    estimated_total_cost: float | None = None


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_services(
    ctx: Context,
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
    """Return all services for the current company.

    Each item contains the service id and its attributes (description, code,
    price, tax code, service group, etc.).
    """
    client = get_client(ctx)
    params: dict[str, str] = {}
    if page is not None:
        params["page[number]"] = str(page)
    if per_page is not None:
        params["page[size]"] = str(per_page)
    try:
        response = await client.get("/api/services", params=params)
    except TOCOnlineError as exc:
        await ctx.error(f"list_services failed: {exc}")
        raise ToolError(str(exc))

    data = response.get("data", [])
    if not isinstance(data, list):
        data = [data]

    items = [{"id": item.get("id"), **item.get("attributes", {})} for item in data]
    meta = response.get("meta", {})
    return {"data": items, "meta": meta}


@write_tool
async def create_service(
    ctx: Context,
    attributes: Annotated[
        ServiceAttributes,
        Field(description="Service data to create."),
    ],
) -> dict[str, Any]:
    """Create a new service in the catalog.

    Returns the newly created service record including its assigned ID.
    """
    client = get_client(ctx)
    payload = {
        "data": [
            {
                "type": "services",
                "attributes": {
                    **attributes.model_dump(exclude_none=True),
                    "type": "Service",
                },
            }
        ]
    }
    try:
        response = await client.post("/api/services", json=payload)
    except TOCOnlineError as exc:
        await ctx.error(f"create_service failed: {exc}")
        raise ToolError(str(exc))

    data = response.get("data", [])
    item = data[0] if isinstance(data, list) and data else (data or {})
    await ctx.info(f"Service created with id={item.get('id')}")
    return {"id": item.get("id"), **item.get("attributes", {})}


@write_tool
async def update_service(
    ctx: Context,
    service_id: Annotated[
        str, Field(description="The TOC Online service ID to update.")
    ],
    attributes: Annotated[
        ServiceUpdateAttributes,
        Field(description="Fields to update (only provided fields are changed)."),
    ],
) -> dict[str, Any]:
    """Update an existing service's attributes.

    Only supply the fields you want to change; omitted fields remain unchanged.
    """
    client = get_client(ctx)
    validate_resource_id(service_id, "service_id")
    payload = {
        "data": {
            "type": "services",
            "id": service_id,
            "attributes": attributes.model_dump(exclude_none=True),
        }
    }
    try:
        response = await client.patch("/api/services", json=payload)
    except TOCOnlineError as exc:
        await ctx.error(f"update_service({service_id}) failed: {exc}")
        raise ToolError(str(exc))

    item = response.get("data", {})
    await ctx.info(f"Service {service_id} updated")
    return {"id": item.get("id"), **item.get("attributes", {})}


@write_tool
async def delete_service(
    ctx: Context,
    service_id: Annotated[
        str, Field(description="The TOC Online service ID to delete.")
    ],
) -> dict[str, Any]:
    """Delete a service by ID.

    Returns a confirmation meta object on success.
    Raises an error if the service is referenced on existing documents.
    """
    client = get_client(ctx)
    validate_resource_id(service_id, "service_id")
    payload = {"data": {"id": service_id, "type": "services"}}
    try:
        response = await client.delete("/api/services", json=payload)
    except TOCOnlineError as exc:
        await ctx.error(f"delete_service({service_id}) failed: {exc}")
        raise ToolError(str(exc))

    await ctx.info(f"Service {service_id} deleted")
    return response.get("meta", {"result": "deleted"})
