"""MCP tools for managing TOC Online Purchase Documents.

Endpoints covered:
  GET    /api/v1/commercial_purchases_documents/
    -> list_purchase_documents
  GET    /api/commercial_purchases_documents/{id}
    -> get_purchase_document  (legacy path, no v1 by-ID endpoint in spec)
  POST   /api/v1/commercial_purchases_documents
    -> create_purchase_document  (atomic, flat payload)
  PATCH  /api/v1/commercial_purchases_documents/{id}/finalize
    -> finalize_purchase_document
  PATCH  /api/v1/commercial_purchases_documents/{id}/void
    -> void_purchase_document
  DELETE /api/commercial_purchases_documents/{id}
    -> delete_purchase_document  (legacy path)

  GET    /api/url_for_print/{id}?filter[type]=PurchasesDocument
    -> get_purchase_document_pdf_url
  PATCH  /api/email/document
    -> send_purchase_document_email

Common purchase document types (document_type):
  FC = Fatura de Compra, VD = Nota de Débito de Fornecedor,
  VC = Nota de Crédito de Fornecedor, CC = Consulta de Preços (quote request)
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


class PurchaseDocumentLine(BaseModel):
    """A single line on a purchase document (v1 atomic create)."""

    item_id: Annotated[
        int,
        Field(
            description="ID of the product or service from /api/products or"
            " /api/services."
        ),
    ]
    item_type: Annotated[
        str,
        Field(description="'Product' or 'Service'."),
    ]
    quantity: Annotated[
        float | None,
        Field(default=None, description="Quantity (defaults to 1)."),
    ] = None
    unit_price: Annotated[
        float | None,
        Field(
            default=None,
            description="Unit price before tax. If omitted, the item default is used.",
        ),
    ] = None
    tax_id: Annotated[
        int | None,
        Field(
            default=None,
            description="Tax ID from /api/taxes. If omitted the item default is used.",
        ),
    ] = None
    unit_of_measure_id: Annotated[
        int | None,
        Field(
            default=None, description="Unit of measure ID from /api/units_of_measure."
        ),
    ] = None
    discount: Annotated[
        float | None,
        Field(default=None, description="Line discount percentage (0-100)."),
    ] = None
    description: Annotated[
        str | None,
        Field(default=None, description="Optional line description override."),
    ] = None
    expense_category_id: Annotated[
        int | None,
        Field(
            default=None,
            description="Expense category ID from /api/expense_categories.",
        ),
    ] = None


class PurchaseDocumentAttributes(BaseModel):
    """Attributes for creating a new purchase document
    (v1 atomic endpoint — flat payload)."""

    document_type: Annotated[
        str,
        Field(
            description="Document type code (e.g. 'FC' = Fatura de Compra,"
            " 'VD' = Nota de Débito, 'VC' = Nota de Crédito)."
        ),
    ]
    document_series_id: Annotated[
        int,
        Field(description="Document series ID from /api/commercial_document_series."),
    ]
    date: Annotated[
        str,
        Field(description="Document date in ISO 8601 format (YYYY-MM-DD)."),
    ]
    supplier_id: Annotated[
        int,
        Field(description="Supplier ID from /api/suppliers."),
    ]
    due_date: Annotated[
        str | None,
        Field(default=None, description="Payment due date (YYYY-MM-DD)."),
    ] = None
    external_reference: Annotated[
        str | None,
        Field(default=None, description="Supplier's own invoice/document number."),
    ] = None
    supplier_business_name: Annotated[
        str | None,
        Field(
            default=None, description="Supplier name to stamp on the document header."
        ),
    ] = None
    supplier_tax_registration_number: Annotated[
        str | None,
        Field(
            default=None, description="Supplier NIF to stamp on the document header."
        ),
    ] = None
    supplier_address_detail: Annotated[
        str | None,
        Field(
            default=None, description="Supplier street address for the document header."
        ),
    ] = None
    supplier_city: Annotated[
        str | None,
        Field(default=None, description="Supplier city for the document header."),
    ] = None
    supplier_postcode: Annotated[
        str | None,
        Field(default=None, description="Supplier postcode for the document header."),
    ] = None
    supplier_country: Annotated[
        str | None,
        Field(
            default=None, description="Supplier country ISO alpha-2 code (e.g. 'PT')."
        ),
    ] = None
    currency_id: Annotated[
        int | None,
        Field(
            default=None,
            description="Currency ID from /api/currencies"
            " (default = company currency).",
        ),
    ] = None
    currency_iso_code: Annotated[
        str | None,
        Field(default=None, description="ISO 4217 currency code (e.g. 'EUR', 'USD')."),
    ] = None
    currency_conversion_rate: Annotated[
        float | None,
        Field(
            default=None,
            description="Exchange rate to company currency when currency_id is set.",
        ),
    ] = None
    settlement_expression: Annotated[
        str | None,
        Field(default=None, description="Header discount expression (e.g. '7.5')."),
    ] = None
    retention_total: Annotated[
        float | None,
        Field(default=None, description="Retention amount to withhold."),
    ] = None
    retention_type: Annotated[
        str | None,
        Field(
            default=None,
            description="Retention type (e.g. 'TD' = Taxa Definitiva, 'IRS', 'IRC').",
        ),
    ] = None
    tax_exemption_reason_id: Annotated[
        int | None,
        Field(
            default=None,
            description="Tax exemption reason ID from /api/tax_exemption_reasons.",
        ),
    ] = None
    vat_included_prices: Annotated[
        bool | None,
        Field(default=None, description="Whether unit prices already include VAT."),
    ] = None
    notes: Annotated[
        str | None,
        Field(default=None, description="Printed observations on the document."),
    ] = None
    lines: Annotated[
        list[PurchaseDocumentLine] | None,
        Field(
            default=None,
            description="Document lines to create atomically with the header.",
        ),
    ] = None


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_purchase_documents(
    ctx: Context,
    status: Annotated[
        str | None,
        Field(
            default=None,
            description="Filter by document status: '1' = finalized, '0' = draft."
            " Omit for all.",
        ),
    ] = None,
    document_no: Annotated[
        str | None,
        Field(
            default=None,
            description="Filter by document number (e.g. 'FF 2025/1'). Maps to"
            " filter[document_no].",
        ),
    ] = None,
    supplier_id: Annotated[
        str | None,
        Field(
            default=None,
            description="Filter by supplier ID (numeric string). Maps to"
            " filter[supplier_id].",
        ),
    ] = None,
    supplier_tax_registration_number: Annotated[
        str | None,
        Field(
            default=None,
            description="Filter by supplier NIF (tax registration number). Maps to"
            " filter[supplier_tax_registration_number].",
        ),
    ] = None,
    date_from: Annotated[
        str | None,
        Field(
            default=None,
            description="Return documents on or after this date (YYYY-MM-DD)."
            " Maps to filter[date_from].",
        ),
    ] = None,
    date_to: Annotated[
        str | None,
        Field(
            default=None,
            description="Return documents on or before this date (YYYY-MM-DD)."
            " Maps to filter[date_to].",
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
    """Return all purchase documents for the current company.

    Each item contains the document id and its attributes (type, date, supplier,
    totals, status, etc.). Filter by ``status``, ``document_no``, ``supplier_id``,
    ``supplier_tax_registration_number``, or date range to narrow results.
    """
    client = get_client(ctx)
    params: dict[str, str] = {}
    if status:
        params["filter[status]"] = status
    if document_no:
        params["filter[document_no]"] = document_no
    if supplier_id:
        params["filter[supplier_id]"] = supplier_id
    if supplier_tax_registration_number:
        params["filter[supplier_tax_registration_number]"] = (
            supplier_tax_registration_number
        )
    if date_from:
        params["filter[date_from]"] = date_from
    if date_to:
        params["filter[date_to]"] = date_to
    if page is not None:
        params["page[number]"] = str(page)
    if per_page is not None:
        params["page[size]"] = str(per_page)

    try:
        response = await client.get(
            "/api/v1/commercial_purchases_documents/", params=params
        )
    except TOCOnlineError as exc:
        await ctx.error(f"list_purchase_documents failed: {exc}")
        raise ToolError(str(exc)) from exc

    data = response.get("data", [])
    if not isinstance(data, list):
        data = [data]

    items = [{"id": item.get("id"), **item.get("attributes", {})} for item in data]
    meta = response.get("meta", {})
    return {"data": items, "meta": meta}


@mcp.tool()
async def get_purchase_document(
    ctx: Context,
    document_id: Annotated[
        str, Field(description="The TOC Online purchase document ID.")
    ],
) -> dict[str, Any]:
    """Return a single purchase document by ID including all attributes
    and line references."""
    client = get_client(ctx)
    validate_resource_id(document_id, "document_id")
    try:
        response = await client.get(
            f"/api/commercial_purchases_documents/{document_id}"
        )
    except TOCOnlineError as exc:
        await ctx.error(f"get_purchase_document({document_id}) failed: {exc}")
        raise ToolError(str(exc)) from exc

    item = response.get("data", {})
    return {"id": item.get("id"), **item.get("attributes", {})}


@write_tool
async def create_purchase_document(
    ctx: Context,
    attributes: Annotated[
        PurchaseDocumentAttributes,
        Field(description="Purchase document header and optional lines."),
    ],
) -> dict[str, Any]:
    """Create a new purchase document atomically (header + lines in one request).

    Uses the v1 endpoint which accepts lines nested inside the payload.
    The document starts in *draft* status; call ``finalize_purchase_document``
    to lock it.  Returns the newly created document with its assigned ID.
    """
    client = get_client(ctx)
    # v1 endpoint uses a flat payload (no JSON:API wrapper)
    # model_dump already converts nested Pydantic models to plain dicts
    payload = attributes.model_dump(exclude_none=True)
    try:
        response = await client.post(
            "/api/v1/commercial_purchases_documents", json=payload
        )
    except TOCOnlineError as exc:
        await ctx.error(f"create_purchase_document failed: {exc}")
        raise ToolError(str(exc)) from exc

    item = response.get("data", {})
    await ctx.info(f"Purchase document created with id={item.get('id')}")
    return {"id": item.get("id"), **item.get("attributes", {})}


@write_tool
async def finalize_purchase_document(
    ctx: Context,
    document_id: Annotated[
        str, Field(description="The TOC Online purchase document ID to finalize.")
    ],
) -> dict[str, Any]:
    """Finalize (lock) a draft purchase document making it legally binding.

    Sets the document status to 1 (final). Finalized documents cannot be edited
    or deleted — only cancelled via a credit note.
    """
    client = get_client(ctx)
    validate_resource_id(document_id, "document_id")
    # v1 finalize: PATCH /api/v1/commercial_purchases_documents/{id}/finalize
    try:
        response = await client.patch(
            f"/api/v1/commercial_purchases_documents/{document_id}/finalize", json={}
        )
    except TOCOnlineError as exc:
        await ctx.error(f"finalize_purchase_document({document_id}) failed: {exc}")
        raise ToolError(str(exc)) from exc

    # The finalize endpoint returns a flat JSON object (no data/attributes wrapper).
    await ctx.info(f"Purchase document {document_id} finalized")
    return response


@write_tool
async def delete_purchase_document(
    ctx: Context,
    document_id: Annotated[
        str, Field(description="The TOC Online purchase document ID to delete.")
    ],
) -> dict[str, Any]:
    """Delete a draft purchase document by ID.

    Only documents in draft status can be deleted. Returns a confirmation meta
    object on success.
    """
    client = get_client(ctx)
    validate_resource_id(document_id, "document_id")
    try:
        response = await client.delete(
            f"/api/commercial_purchases_documents/{document_id}"
        )
    except TOCOnlineError as exc:
        await ctx.error(f"delete_purchase_document({document_id}) failed: {exc}")
        raise ToolError(str(exc)) from exc

    await ctx.info(f"Purchase document {document_id} deleted")
    return response.get("meta", {"result": "deleted"})


@mcp.tool()
async def get_purchase_document_pdf_url(
    ctx: Context,
    document_id: Annotated[
        str, Field(description="The TOC Online purchase document ID.")
    ],
) -> dict[str, Any]:
    """Return the PDF download URL for a finalized purchase document."""
    client = get_client(ctx)
    validate_resource_id(document_id, "document_id")
    try:
        response = await client.get(
            f"/api/url_for_print/{document_id}",
            params={"filter[type]": "PurchasesDocument"},
        )
    except TOCOnlineError as exc:
        await ctx.error(f"get_purchase_document_pdf_url({document_id}) failed: {exc}")
        raise ToolError(str(exc)) from exc

    data = response.get("data", {})
    attrs = data.get("attributes", {})
    url_obj = attrs.get("url", attrs)
    if isinstance(url_obj, dict) and url_obj.get("host"):
        scheme = url_obj.get("scheme", "https")
        host = url_obj.get("host", "")
        path = url_obj.get("path", "")
        port = url_obj.get("port", 443)
        full_url = f"{scheme}://{host}:{port}{path}"
        return {"id": data.get("id"), "full_url": full_url, **url_obj}
    return {"id": data.get("id"), **attrs}


@write_tool
async def send_purchase_document_email(
    ctx: Context,
    document_id: Annotated[
        str, Field(description="The TOC Online purchase document ID to email.")
    ],
    to_email: Annotated[str, Field(description="Recipient email address.")],
    from_email: Annotated[str, Field(description="Sender email address.")],
    from_name: Annotated[str, Field(description="Sender display name.")],
    subject: Annotated[str, Field(description="Email subject line.")],
) -> dict[str, Any]:
    """Send a purchase document by email.

    Returns the API response (usually an empty meta object on success).
    """
    client = get_client(ctx)
    validate_resource_id(document_id, "document_id")
    payload = {
        "data": {
            "type": "email/document",
            "id": document_id,
            "attributes": {
                "to_email": to_email,
                "from_email": from_email,
                "from_name": from_name,
                "subject": subject,
                "type": "PurchasesDocument",
            },
        }
    }
    try:
        response = await client.patch("/api/email/document", json=payload)
    except TOCOnlineError as exc:
        await ctx.error(f"send_purchase_document_email({document_id}) failed: {exc}")
        raise ToolError(str(exc)) from exc

    await ctx.info(f"Purchase document {document_id} emailed to {to_email}")
    return response.get("meta", response.get("data", {"result": "sent"}))


@write_tool
async def void_purchase_document(
    ctx: Context,
    document_id: Annotated[
        str, Field(description="The TOC Online purchase document ID to void (anular).")
    ],
) -> dict[str, Any]:
    """Void (anular) a finalized purchase document.

    Only finalized documents can be voided. Voiding is irreversible.
    Returns the API response on success.
    """
    client = get_client(ctx)
    validate_resource_id(document_id, "document_id")
    try:
        response = await client.patch(
            f"/api/v1/commercial_purchases_documents/{document_id}/void", json={}
        )
    except TOCOnlineError as exc:
        await ctx.error(f"void_purchase_document({document_id}) failed: {exc}")
        raise ToolError(str(exc)) from exc

    await ctx.info(f"Purchase document {document_id} voided")
    return response.get("meta", response.get("data", {"result": "voided"}))
