"""MCP tools for managing TOC Online Purchase Payments.

Endpoints covered:
  GET    /api/v1/commercial_purchases_payments
    -> list_purchase_payments
  GET    /api/v1/commercial_purchases_payments/{id}
    -> get_purchase_payment
  POST   /api/v1/commercial_purchases_payments
    -> create_purchase_payment  (flat JSON body)
  PATCH  /api/commercial_purchases_payments/{id}
    -> update_purchase_payment  (legacy path, JSON:API body)
  DELETE /api/commercial_purchases_payments/{id}
    -> delete_purchase_payment  (legacy path)
  PATCH  /api/v1/commercial_purchases_payments/
    -> finalize payment (not exposed as tool)
  DELETE /api/v1/commercial_purchases_payments/
    -> bulk remove payments (not exposed as tool)
  DELETE /api/v1/commercial_purchases_payment_lines/
    -> remove payment lines (not exposed as tool)

  GET    /api/commercial_purchases_payment_lines
    -> list_purchase_payment_lines
  POST   /api/commercial_purchases_payment_lines
    -> create_purchase_payment_line

A purchase payment («Pagamento a Fornecedor») records payment against one or more
finalized purchase documents. Each payment line links to a payable (usually a
PurchaseDocument) via ``payable_id`` / ``payable_type`` and records the
``paid_value``.
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
# Input models
# ---------------------------------------------------------------------------


class PurchasePaymentAttributes(BaseModel):
    """Attributes for creating a new purchase payment header."""

    date: Annotated[
        str,
        Field(description="Payment date in ISO 8601 format (YYYY-MM-DD)."),
    ]
    document_series_id: Annotated[
        int,
        Field(
            description="Payment document series ID from"
            " /api/commercial_document_series."
        ),
    ]
    gross_total: Annotated[
        float,
        Field(description="Total gross amount paid."),
    ]
    net_total: Annotated[
        float,
        Field(description="Total net amount paid (before VAT)."),
    ]
    payment_mechanism: Annotated[
        str,
        Field(
            description="Payment mechanism code (e.g. 'TB' = bank transfer,"
            " 'MO' = cash)."
        ),
    ]
    supplier_id: Annotated[
        int | None,
        Field(
            default=None,
            description="Supplier ID from /api/suppliers. Preferred over"
            " third_party_id for the v1 endpoint.",
        ),
    ] = None
    third_party_id: Annotated[
        int | None,
        Field(default=None, description="Third-party ID (alternative to supplier_id)."),
    ] = None
    third_party_type: Annotated[
        str | None,
        Field(
            default=None,
            description="Third-party type — typically 'Supplier'. Only needed"
            " when using third_party_id.",
        ),
    ] = None
    cash_account_id: Annotated[
        int | None,
        Field(default=None, description="Cash account ID from /api/cash_accounts."),
    ] = None
    check_number: Annotated[
        str | None,
        Field(
            default=None, description="Cheque number (if payment mechanism is cheque)."
        ),
    ] = None
    currency_id: Annotated[
        int | None,
        Field(
            default=None,
            description="Currency ID from /api/currencies. Defaults to the"
            " company base currency.",
        ),
    ] = None
    currency_conversion_rate: Annotated[
        float | None,
        Field(
            default=None,
            description="Exchange rate relative to base currency. Omit (or set"
            " 1.0) for base currency payments.",
        ),
    ] = None
    observations: Annotated[
        str | None,
        Field(default=None, description="Visible observations printed on the payment."),
    ] = None
    internal_observations: Annotated[
        str | None,
        Field(default=None, description="Internal (private) observations."),
    ] = None


class PurchasePaymentUpdateAttributes(BaseModel):
    """Attributes that can be updated on an existing purchase payment (all optional)."""

    date: str | None = None
    document_series_id: int | None = None
    document_no: str | None = None
    gross_total: float | None = None
    net_total: float | None = None
    payment_mechanism: str | None = None
    cash_account_id: int | None = None
    check_number: str | None = None
    currency_conversion_rate: float | None = None
    third_party_id: int | None = None
    third_party_type: str | None = None
    standalone: bool | None = None
    deleted: bool | None = None
    observations: str | None = None
    internal_observations: str | None = None


class PurchasePaymentLineAttributes(BaseModel):
    """Attributes for creating a line on a purchase payment."""

    payment_id: Annotated[
        int,
        Field(description="ID of the payment header this line belongs to."),
    ]
    payable_id: Annotated[
        int,
        Field(description="ID of the purchase document being settled."),
    ]
    payable_type: Annotated[
        str,
        Field(
            description=(
                "Type of the payable. Use 'Purchases::Document' to settle a"
                " purchase document "
                "or 'Purchases::DocumentLine' to settle a specific purchase"
                " document line."
            )
        ),
    ]
    paid_value: Annotated[
        float,
        Field(description="Amount paid against this purchase document."),
    ]
    settlement_percentage: Annotated[
        float | None,
        Field(default=None, description="Discount/settlement percentage applied."),
    ] = None
    gross_total: Annotated[
        float | None,
        Field(default=None, description="Gross total of the payable document."),
    ] = None
    net_total: Annotated[
        float | None,
        Field(default=None, description="Net total of the payable document."),
    ] = None
    retention_total: Annotated[
        float | None,
        Field(default=None, description="Retention amount withheld."),
    ] = None
    settlement_amount: Annotated[
        float | None,
        Field(default=None, description="Settlement discount amount applied."),
    ] = None
    cashed_vat_amount: Annotated[
        float | None,
        Field(default=None, description="Cashed VAT amount (regime de IVA de caixa)."),
    ] = None


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_purchase_payments(
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
    """Return all purchase payments for the current company.

    Each item contains the payment id and its attributes (date, totals,
    payment mechanism, supplier, etc.).
    """
    client = get_client(ctx)
    params: dict[str, str] = {}
    if page is not None:
        params["page[number]"] = str(page)
    if per_page is not None:
        params["page[size]"] = str(per_page)
    try:
        response = await client.get(
            "/api/v1/commercial_purchases_payments", params=params
        )
    except TOCOnlineError as exc:
        await ctx.error(f"list_purchase_payments failed: {exc}")
        raise ToolError(str(exc)) from exc

    data = response.get("data", [])
    if not isinstance(data, list):
        data = [data]

    items = [{"id": item.get("id"), **item.get("attributes", {})} for item in data]
    meta = response.get("meta", {})
    return {"data": items, "meta": meta}


@mcp.tool()
async def get_purchase_payment(
    ctx: Context,
    payment_id: Annotated[
        str, Field(description="The TOC Online purchase payment ID.")
    ],
) -> dict[str, Any]:
    """Return a single purchase payment by ID including all attributes
    and line references."""
    client = get_client(ctx)
    validate_resource_id(payment_id, "payment_id")
    try:
        response = await client.get(
            f"/api/v1/commercial_purchases_payments/{payment_id}"
        )
    except TOCOnlineError as exc:
        await ctx.error(f"get_purchase_payment({payment_id}) failed: {exc}")
        raise ToolError(str(exc)) from exc

    item = response.get("data", {})
    return {"id": item.get("id"), **item.get("attributes", {})}


@write_tool
async def create_purchase_payment(
    ctx: Context,
    attributes: Annotated[
        PurchasePaymentAttributes,
        Field(
            description=(
                "Payment header data. Add lines separately with "
                "create_purchase_payment_line to link to purchase documents."
            )
        ),
    ],
) -> dict[str, Any]:
    """Create a new purchase payment header.

    After creating the header, add lines with ``create_purchase_payment_line`` to
    link it to one or more finalized purchase documents.
    Returns the newly created payment with its assigned ID.
    """
    client = get_client(ctx)
    # v1 endpoint expects a flat JSON body (no JSON:API data wrapper)
    payload = attributes.model_dump(exclude_none=True)
    try:
        response = await client.post(
            "/api/v1/commercial_purchases_payments", json=payload
        )
    except TOCOnlineError as exc:
        await ctx.error(f"create_purchase_payment failed: {exc}")
        raise ToolError(str(exc)) from exc

    item = response.get("data", {})
    await ctx.info(f"Purchase payment created with id={item.get('id')}")
    return {"id": item.get("id"), **item.get("attributes", {})}


@write_tool
async def update_purchase_payment(
    ctx: Context,
    payment_id: Annotated[
        str, Field(description="The TOC Online purchase payment ID to update.")
    ],
    attributes: Annotated[
        PurchasePaymentUpdateAttributes,
        Field(description="Fields to update (only provided fields are changed)."),
    ],
) -> dict[str, Any]:
    """Update an existing purchase payment's header attributes.

    Only supply the fields you want to change; omitted fields remain unchanged.
    """
    client = get_client(ctx)
    validate_resource_id(payment_id, "payment_id")
    payload = {
        "data": {
            "type": "commercial_purchases_payments",
            "id": payment_id,
            "attributes": attributes.model_dump(exclude_none=True),
        }
    }
    try:
        # UPDATE uses the legacy path — the v1 PATCH at
        # /api/v1/commercial_purchases_payments/ is
        # for bulk/finalize operations, not per-record updates.
        response = await client.patch(
            f"/api/commercial_purchases_payments/{payment_id}", json=payload
        )
    except TOCOnlineError as exc:
        await ctx.error(f"update_purchase_payment({payment_id}) failed: {exc}")
        raise ToolError(str(exc)) from exc

    item = response.get("data", {})
    await ctx.info(f"Purchase payment {payment_id} updated")
    return {"id": item.get("id"), **item.get("attributes", {})}


@write_tool
async def delete_purchase_payment(
    ctx: Context,
    payment_id: Annotated[
        str, Field(description="The TOC Online purchase payment ID to delete.")
    ],
) -> dict[str, Any]:
    """Delete a purchase payment by ID.

    Returns a confirmation meta object on success.
    """
    client = get_client(ctx)
    validate_resource_id(payment_id, "payment_id")
    try:
        # DELETE uses the legacy path — the v1 DELETE at
        # /api/v1/commercial_purchases_payments/ is
        # a bulk remove, not per-record.
        response = await client.delete(
            f"/api/commercial_purchases_payments/{payment_id}"
        )
    except TOCOnlineError as exc:
        await ctx.error(f"delete_purchase_payment({payment_id}) failed: {exc}")
        raise ToolError(str(exc)) from exc

    await ctx.info(f"Purchase payment {payment_id} deleted")
    return response.get("meta", {"result": "deleted"})


@mcp.tool()
async def list_purchase_payment_lines(
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
    """Return all purchase payment lines for the current company.

    Each line records the amount paid against a specific purchase document.
    """
    client = get_client(ctx)
    params: dict[str, str] = {}
    if page is not None:
        params["page[number]"] = str(page)
    if per_page is not None:
        params["page[size]"] = str(per_page)
    try:
        response = await client.get(
            "/api/commercial_purchases_payment_lines", params=params
        )
    except TOCOnlineError as exc:
        await ctx.error(f"list_purchase_payment_lines failed: {exc}")
        raise ToolError(str(exc)) from exc

    data = response.get("data", [])
    if not isinstance(data, list):
        data = [data]

    items = [{"id": item.get("id"), **item.get("attributes", {})} for item in data]
    meta = response.get("meta", {})
    return {"data": items, "meta": meta}


@write_tool
async def create_purchase_payment_line(
    ctx: Context,
    attributes: Annotated[
        PurchasePaymentLineAttributes,
        Field(
            description="Payment line data linking the payment to a purchase document."
        ),
    ],
) -> dict[str, Any]:
    """Add a line to an existing purchase payment linking it to a purchase document.

    Each line records how much was paid (``paid_value``) against a specific
    purchase document (``payable_id`` / ``payable_type='Purchases::Document'``).
    """
    client = get_client(ctx)
    payload = {
        "data": {
            "type": "commercial_purchases_payment_lines",
            "attributes": attributes.model_dump(exclude_none=True),
        }
    }
    try:
        response = await client.post(
            "/api/commercial_purchases_payment_lines", json=payload
        )
    except TOCOnlineError as exc:
        await ctx.error(f"create_purchase_payment_line failed: {exc}")
        raise ToolError(str(exc)) from exc

    item = response.get("data", {})
    await ctx.info(f"Purchase payment line created with id={item.get('id')}")
    return {"id": item.get("id"), **item.get("attributes", {})}
