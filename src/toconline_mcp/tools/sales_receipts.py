"""MCP tools for managing TOC Online Sales Receipts.

Endpoints covered:
  GET    /api/v1/commercial_sales_receipts               -> list_sales_receipts
  GET    /api/v1/commercial_sales_receipts/{id}          -> get_sales_receipt
  POST   /api/v1/commercial_sales_receipts               -> create_sales_receipt
  PATCH  /api/v1/commercial_sales_receipts/{id}          -> update_sales_receipt
  DELETE /api/v1/commercial_sales_receipts/{id}          -> delete_sales_receipt

  GET    /api/commercial_sales_receipt_lines              -> list_sales_receipt_lines
  POST   /api/commercial_sales_receipt_lines              -> create_sales_receipt_line
  DELETE /api/v1/commercial_sales_receipt_lines/          -> delete_sales_receipt_lines
  PATCH  /api/v1/commercial_sales_receipts/{id}/void     -> void_sales_receipt

  PATCH  /api/email/document (type=Receipt)           -> send_sales_receipt_email

A receipt («Recibo de Venda») records payment against one or more finalized sales
documents. Each receipt line links to a receivable (usually a Document) via
``receivable_id`` / ``receivable_type`` and records the ``received_value``.
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


class SalesReceiptAttributes(BaseModel):
    """Attributes for creating a new sales receipt header (v1 flat-body format)."""

    date: Annotated[
        str,
        Field(description="Receipt date in ISO 8601 format (YYYY-MM-DD)."),
    ]
    gross_total: Annotated[
        float,
        Field(description="Total gross amount received."),
    ]
    net_total: Annotated[
        float,
        Field(description="Total net amount received (before VAT)."),
    ]
    payment_mechanism: Annotated[
        str,
        Field(
            description="Payment mechanism code (e.g. 'MO' = cash, 'TB' = bank"
            " transfer)."
        ),
    ]
    customer_id: Annotated[
        int | None,
        Field(default=None, description="Customer ID to associate with this receipt."),
    ] = None
    cash_account_id: Annotated[
        int | None,
        Field(default=None, description="Cash account ID from /api/cash_accounts."),
    ] = None
    check_number: Annotated[
        str | None,
        Field(default=None, description="Cheque number, if payment was by cheque."),
    ] = None
    standalone: Annotated[
        bool | None,
        Field(
            default=None,
            description="Whether this is a standalone receipt (not linked to a"
            " document).",
        ),
    ] = None
    third_party_id: Annotated[
        int | None,
        Field(default=None, description="Third-party entity ID, if applicable."),
    ] = None
    third_party_type: Annotated[
        str | None,
        Field(default=None, description="Third-party entity type, if applicable."),
    ] = None
    document_series_id: Annotated[
        int | None,
        Field(
            default=None,
            description="Document series ID from /api/commercial_document_series.",
        ),
    ] = None
    currency_id: Annotated[
        int | None,
        Field(
            default=None,
            description="Currency ID from /api/currencies (defaults to company's"
            " base currency).",
        ),
    ] = None
    currency_conversion_rate: Annotated[
        float | None,
        Field(
            default=None,
            description="Exchange rate to the company's base currency (1.0 for EUR).",
        ),
    ] = None
    country_id: Annotated[
        int | None,
        Field(default=None, description="Country ID from /api/countries."),
    ] = None
    observations: Annotated[
        str | None,
        Field(default=None, description="Visible observations printed on the receipt."),
    ] = None
    internal_observations: Annotated[
        str | None,
        Field(default=None, description="Internal (private) observations."),
    ] = None


class SalesReceiptUpdateAttributes(BaseModel):
    """Attributes that can be updated on an existing sales receipt
    (v1 flat-body; all optional)."""

    date: str | None = None
    gross_total: float | None = None
    net_total: float | None = None
    payment_mechanism: str | None = None
    customer_id: int | None = None
    cash_account_id: int | None = None
    check_number: str | None = None
    document_series_id: int | None = None
    standalone: bool | None = None
    third_party_id: int | None = None
    third_party_type: str | None = None
    observations: str | None = None
    internal_observations: str | None = None


class SalesReceiptLineAttributes(BaseModel):
    """Attributes for creating a line on a sales receipt."""

    receipt_id: Annotated[
        int,
        Field(description="ID of the receipt header this line belongs to."),
    ]
    receivable_id: Annotated[
        int,
        Field(description="ID of the document being settled (sales document ID)."),
    ]
    receivable_type: Annotated[
        str,
        Field(description="Type of the receivable — typically 'Document'."),
    ]
    received_value: Annotated[
        float,
        Field(description="Amount received against this document."),
    ]
    settlement_percentage: Annotated[
        str | None,
        Field(
            default=None,
            description="Discount/settlement percentage applied (passed as string"
            " expression, e.g. '3' for 3%).",
        ),
    ] = None
    settlement_amount: Annotated[
        float | None,
        Field(
            default=None, description="Absolute settlement (discount) amount applied."
        ),
    ] = None
    cashed_vat_amount: Annotated[
        float | None,
        Field(
            default=None,
            description="Cashed VAT amount for this line (cashed-VAT schemes).",
        ),
    ] = None
    gross_total: Annotated[
        float | None,
        Field(default=None, description="Gross total of the receivable document."),
    ] = None
    net_total: Annotated[
        float | None,
        Field(default=None, description="Net total of the receivable document."),
    ] = None
    retention_total: Annotated[
        float | None,
        Field(default=None, description="Retention amount withheld."),
    ] = None


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_sales_receipts(
    ctx: Context,
    document_no: Annotated[
        str | None,
        Field(
            default=None,
            description="Filter by document number (e.g. 'RG 2025/1'). Maps to"
            " filter[document_no].",
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
    """Return all sales receipts for the current company.

    Each item contains the receipt id and its attributes (date, totals,
    payment mechanism, linked document lines, etc.).
    Filter by ``document_no`` to find a specific receipt by its printed number.
    """
    client = get_client(ctx)
    params: dict[str, str] = {}
    if document_no:
        params["filter[document_no]"] = document_no
    if page is not None:
        params["page[number]"] = str(page)
    if per_page is not None:
        params["page[size]"] = str(per_page)
    try:
        response = await client.get("/api/v1/commercial_sales_receipts", params=params)
    except TOCOnlineError as exc:
        await ctx.error(f"list_sales_receipts failed: {exc}")
        raise ToolError(str(exc)) from exc

    data = response.get("data", [])
    if not isinstance(data, list):
        data = [data]

    items = [{"id": item.get("id"), **item.get("attributes", {})} for item in data]
    meta = response.get("meta", {})
    return {"data": items, "meta": meta}


@mcp.tool()
async def get_sales_receipt(
    ctx: Context,
    receipt_id: Annotated[str, Field(description="The TOC Online sales receipt ID.")],
) -> dict[str, Any]:
    """Return a single sales receipt by ID, including all attributes
    and line references."""
    client = get_client(ctx)
    validate_resource_id(receipt_id, "receipt_id")
    try:
        response = await client.get(f"/api/v1/commercial_sales_receipts/{receipt_id}")
    except TOCOnlineError as exc:
        await ctx.error(f"get_sales_receipt({receipt_id}) failed: {exc}")
        raise ToolError(str(exc)) from exc

    item = response.get("data", {})
    return {"id": item.get("id"), **item.get("attributes", {})}


@write_tool
async def create_sales_receipt(
    ctx: Context,
    attributes: Annotated[
        SalesReceiptAttributes,
        Field(
            description="Receipt header data. Add lines separately with"
            " create_sales_receipt_line."
        ),
    ],
) -> dict[str, Any]:
    """Create a new sales receipt header.

    After creating the header, add lines with ``create_sales_receipt_line`` to link
    it to one or more finalized sales documents.
    Returns the newly created receipt with its assigned ID.
    """
    client = get_client(ctx)
    # v1 endpoint expects a flat JSON body (not JSON:API wrapper)
    payload = attributes.model_dump(exclude_none=True)
    try:
        response = await client.post("/api/v1/commercial_sales_receipts", json=payload)
    except TOCOnlineError as exc:
        await ctx.error(f"create_sales_receipt failed: {exc}")
        raise ToolError(str(exc)) from exc

    item = response.get("data", {})
    await ctx.info(f"Sales receipt created with id={item.get('id')}")
    return {"id": item.get("id"), **item.get("attributes", {})}


@write_tool
async def update_sales_receipt(
    ctx: Context,
    receipt_id: Annotated[
        str, Field(description="The TOC Online sales receipt ID to update.")
    ],
    attributes: Annotated[
        SalesReceiptUpdateAttributes,
        Field(description="Fields to update (only provided fields are changed)."),
    ],
) -> dict[str, Any]:
    """Update an existing sales receipt's header attributes.

    Only supply the fields you want to change; omitted fields remain unchanged.
    """
    client = get_client(ctx)
    validate_resource_id(receipt_id, "receipt_id")
    # v1 endpoint expects a flat JSON body (not JSON:API wrapper)
    payload = attributes.model_dump(exclude_none=True)
    try:
        response = await client.patch(
            f"/api/v1/commercial_sales_receipts/{receipt_id}", json=payload
        )
    except TOCOnlineError as exc:
        await ctx.error(f"update_sales_receipt({receipt_id}) failed: {exc}")
        raise ToolError(str(exc)) from exc

    item = response.get("data", {})
    await ctx.info(f"Sales receipt {receipt_id} updated")
    return {"id": item.get("id"), **item.get("attributes", {})}


@write_tool
async def delete_sales_receipt(
    ctx: Context,
    receipt_id: Annotated[
        str, Field(description="The TOC Online sales receipt ID to delete.")
    ],
) -> dict[str, Any]:
    """Delete a sales receipt by ID.

    Returns a confirmation meta object on success.
    Raises an error if the receipt has already been finalized or cannot be deleted.
    """
    client = get_client(ctx)
    validate_resource_id(receipt_id, "receipt_id")
    try:
        response = await client.delete(
            f"/api/v1/commercial_sales_receipts/{receipt_id}"
        )
    except TOCOnlineError as exc:
        await ctx.error(f"delete_sales_receipt({receipt_id}) failed: {exc}")
        raise ToolError(str(exc)) from exc

    await ctx.info(f"Sales receipt {receipt_id} deleted")
    return response.get("meta", {"result": "deleted"})


@mcp.tool()
async def list_sales_receipt_lines(
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
    """Return all sales receipt lines for the current company.

    Each line records the amount received against a specific sales document.
    """
    client = get_client(ctx)
    params: dict[str, str] = {}
    if page is not None:
        params["page[number]"] = str(page)
    if per_page is not None:
        params["page[size]"] = str(per_page)
    try:
        # GET is only documented at the non-v1 path; v1 only exposes DELETE
        # on receipt lines
        response = await client.get(
            "/api/commercial_sales_receipt_lines", params=params
        )
    except TOCOnlineError as exc:
        await ctx.error(f"list_sales_receipt_lines failed: {exc}")
        raise ToolError(str(exc)) from exc

    data = response.get("data", [])
    if not isinstance(data, list):
        data = [data]

    items = [{"id": item.get("id"), **item.get("attributes", {})} for item in data]
    meta = response.get("meta", {})
    return {"data": items, "meta": meta}


@write_tool
async def create_sales_receipt_line(
    ctx: Context,
    attributes: Annotated[
        SalesReceiptLineAttributes,
        Field(description="Receipt line data linking the receipt to a sales document."),
    ],
) -> dict[str, Any]:
    """Add a line to an existing sales receipt linking it to a sales document.

    Each line records how much was received (``received_value``) against a specific
    sales document (``receivable_id`` / ``receivable_type='Document'``).
    """
    client = get_client(ctx)
    payload = {
        "data": {
            "type": "commercial_sales_receipt_lines",
            "attributes": attributes.model_dump(exclude_none=True),
        }
    }
    try:
        response = await client.post(
            "/api/commercial_sales_receipt_lines", json=payload
        )
    except TOCOnlineError as exc:
        await ctx.error(f"create_sales_receipt_line failed: {exc}")
        raise ToolError(str(exc)) from exc

    item = response.get("data", {})
    await ctx.info(f"Sales receipt line created with id={item.get('id')}")
    return {"id": item.get("id"), **item.get("attributes", {})}


@write_tool
async def send_sales_receipt_email(
    ctx: Context,
    receipt_id: Annotated[
        str, Field(description="The TOC Online sales receipt ID to email.")
    ],
    to_email: Annotated[str, Field(description="Recipient email address.")],
    from_email: Annotated[str, Field(description="Sender email address.")],
    from_name: Annotated[str, Field(description="Sender display name.")],
    subject: Annotated[str, Field(description="Email subject line.")],
) -> dict[str, Any]:
    """Send a sales receipt by email.

    Returns the API response (usually an empty meta object on success).
    """
    client = get_client(ctx)
    validate_resource_id(receipt_id, "receipt_id")
    payload = {
        "data": {
            "type": "email/document",
            "id": receipt_id,
            "attributes": {
                "to_email": to_email,
                "from_email": from_email,
                "from_name": from_name,
                "subject": subject,
                "type": "Receipt",
            },
        }
    }
    try:
        response = await client.patch("/api/email/document", json=payload)
    except TOCOnlineError as exc:
        await ctx.error(f"send_sales_receipt_email({receipt_id}) failed: {exc}")
        raise ToolError(str(exc)) from exc

    await ctx.info(f"Sales receipt {receipt_id} emailed to {to_email}")
    return response.get("meta", response.get("data", {"result": "sent"}))


@write_tool
async def void_sales_receipt(
    ctx: Context,
    receipt_id: Annotated[
        str, Field(description="The TOC Online sales receipt ID to void/annul.")
    ],
) -> dict[str, Any]:
    """Void (annul) a finalized sales receipt.

    Uses the v1 void endpoint: PATCH /api/v1/commercial_sales_receipts/{id}/void.
    Returns the updated receipt record or a confirmation meta object.
    """
    client = get_client(ctx)
    validate_resource_id(receipt_id, "receipt_id")
    try:
        response = await client.patch(
            f"/api/v1/commercial_sales_receipts/{receipt_id}/void", json={}
        )
    except TOCOnlineError as exc:
        await ctx.error(f"void_sales_receipt({receipt_id}) failed: {exc}")
        raise ToolError(str(exc)) from exc

    await ctx.info(f"Sales receipt {receipt_id} voided")
    item = response.get("data", {})
    return (
        {"id": item.get("id"), **item.get("attributes", {})}
        if item
        else response.get("meta", {"result": "voided"})
    )
