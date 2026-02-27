"""MCP tools for managing TOC Online Products.

Endpoints covered:
  GET    /api/products            -> list_products
  POST   /api/products            -> create_product
  PATCH  /api/products            -> update_product  (id embedded in payload)
  DELETE /api/products/{id}       -> delete_product
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


class ProductAttributes(BaseModel):
    """Attributes for creating a new product."""

    item_description: Annotated[
        str,
        Field(description="Product name / description shown on documents."),
    ]
    tax_code: Annotated[
        str,
        Field(description="VAT tax code (e.g. 'NOR', 'INT', 'RED', 'ISE')."),
    ]
    sales_price: Annotated[
        float,
        Field(description="Unit sales price."),
    ]
    item_code: Annotated[
        int | str | None,
        Field(
            default=None,
            description="Internal product code / reference (numeric or string).",
        ),
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
    ean_barcode: Annotated[
        str | None,
        Field(default=None, description="EAN barcode string."),
    ] = None
    accounting_number: Annotated[
        str | None,
        Field(default=None, description="Accounting ledger number for this product."),
    ] = None
    notes: Annotated[
        str | None,
        Field(default=None, description="Internal notes for this product."),
    ] = None
    is_active: Annotated[
        bool | None,
        Field(
            default=None,
            description="Whether the product is active and selectable on documents.",
        ),
    ] = None


class ProductUpdateAttributes(BaseModel):
    """Attributes that can be updated on an existing product (all optional)."""

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
    ean_barcode: str | None = None
    accounting_number: str | None = None
    notes: str | None = None
    is_active: bool | None = None


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_products(
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
    """Return all products for the current company.

    Each item contains the product id and its attributes (description, code,
    price, tax code, etc.).
    """
    client = get_client(ctx)
    params: dict[str, str] = {}
    if page is not None:
        params["page[number]"] = str(page)
    if per_page is not None:
        params["page[size]"] = str(per_page)
    try:
        response = await client.get("/api/products", params=params)
    except TOCOnlineError as exc:
        await ctx.error(f"list_products failed: {exc}")
        raise ToolError(str(exc)) from exc

    data = response.get("data", [])
    if not isinstance(data, list):
        data = [data]

    items = [{"id": item.get("id"), **item.get("attributes", {})} for item in data]
    meta = response.get("meta", {})
    return {"data": items, "meta": meta}


@write_tool
async def create_product(
    ctx: Context,
    attributes: Annotated[
        ProductAttributes,
        Field(description="Product data to create."),
    ],
) -> dict[str, Any]:
    """Create a new product in the catalog.

    Returns the newly created product record including its assigned ID.
    """
    client = get_client(ctx)
    payload = {
        "data": {
            "type": "products",
            "attributes": {
                **attributes.model_dump(exclude_none=True),
                "type": "Product",
            },
        }
    }
    try:
        response = await client.post("/api/products", json=payload)
    except TOCOnlineError as exc:
        await ctx.error(f"create_product failed: {exc}")
        raise ToolError(str(exc)) from exc

    data = response.get("data", {})
    item = data[0] if isinstance(data, list) and data else (data or {})
    await ctx.info(f"Product created with id={item.get('id')}")
    return {"id": item.get("id"), **item.get("attributes", {})}


@write_tool
async def update_product(
    ctx: Context,
    product_id: Annotated[
        str, Field(description="The TOC Online product ID to update.")
    ],
    attributes: Annotated[
        ProductUpdateAttributes,
        Field(description="Fields to update (only provided fields are changed)."),
    ],
) -> dict[str, Any]:
    """Update an existing product's attributes.

    Only supply the fields you want to change; omitted fields remain unchanged.
    """
    client = get_client(ctx)
    validate_resource_id(product_id, "product_id")
    payload = {
        "data": {
            "type": "products",
            "id": product_id,
            "attributes": attributes.model_dump(exclude_none=True),
        }
    }
    try:
        response = await client.patch("/api/products", json=payload)
    except TOCOnlineError as exc:
        await ctx.error(f"update_product({product_id}) failed: {exc}")
        raise ToolError(str(exc)) from exc

    item = response.get("data", {})
    await ctx.info(f"Product {product_id} updated")
    return {"id": item.get("id"), **item.get("attributes", {})}


@write_tool
async def delete_product(
    ctx: Context,
    product_id: Annotated[
        str, Field(description="The TOC Online product ID to delete.")
    ],
) -> dict[str, Any]:
    """Delete a product by ID.

    Returns a confirmation meta object on success.
    Raises an error if the product is referenced on existing documents.
    """
    client = get_client(ctx)
    validate_resource_id(product_id, "product_id")
    try:
        response = await client.delete(f"/api/products/{product_id}")
    except TOCOnlineError as exc:
        await ctx.error(f"delete_product({product_id}) failed: {exc}")
        raise ToolError(str(exc)) from exc

    await ctx.info(f"Product {product_id} deleted")
    return response.get("meta", {"result": "deleted"})
