"""MCP tools for managing TOC Online Sales Documents.

Endpoints covered:
  GET    /api/v1/commercial_sales_documents/           -> list_sales_documents
  GET    /api/v1/commercial_sales_documents/{id}        -> get_sales_document
  POST   /api/v1/commercial_sales_documents           -> create_sales_document  (atomic with lines)
  PATCH  /api/commercial_sales_documents              -> finalize_sales_document (status → 1)  [deprecated endpoint, no v1 equivalent]
  DELETE /api/commercial_sales_documents/{id}         -> delete_sales_document  [deprecated endpoint, no v1 equivalent]

  GET    /api/url_for_print/{id}?filter[type]=Document -> get_sales_document_pdf_url
  PATCH  /api/email/document                           -> send_sales_document_email

Document types:
  FT = Fatura, FS = Fatura Simplificada, FR = Fatura-Recibo, NC = Nota de Crédito,
  ND = Nota de Débito, GT = Guia de Transporte, OR = Orçamento, DC = Documento de Conferência,
  EC = Encomenda do Cliente
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
# Input models
# ---------------------------------------------------------------------------


class SalesDocumentLine(BaseModel):
    """A single line on a sales document (v1 atomic create)."""

    item_id: Annotated[
        int,
        Field(
            description="ID of the product or service from /api/products or /api/services."
        ),
    ]
    item_type: Annotated[
        str,
        Field(description="'Product' or 'Service'."),
    ]
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
    quantity: Annotated[
        float | None,
        Field(default=None, description="Quantity (defaults to 1)."),
    ] = None
    unit_price: Annotated[
        float | None,
        Field(default=None, description="Override the item's default unit price."),
    ] = None
    description: Annotated[
        str | None,
        Field(default=None, description="Override the line description."),
    ] = None
    settlement_expression: Annotated[
        str | None,
        Field(
            default=None, description="Line discount expression, e.g. '10' or '3+5'."
        ),
    ] = None


class SalesDocumentAttributes(BaseModel):
    """Attributes for creating a new sales document via the v1 atomic endpoint."""

    document_type: Annotated[
        str,
        Field(
            description=(
                "Document type code. Common values: 'FT' (Fatura), 'FS' (Fatura Simplificada), "
                "'FR' (Fatura-Recibo), 'NC' (Nota de Crédito), 'ND' (Nota de Débito), "
                "'OR' (Orçamento), 'GT' (Guia de Transporte)."
            )
        ),
    ]
    date: Annotated[
        str,
        Field(description="Document date in ISO 8601 format (YYYY-MM-DD)."),
    ]
    customer_tax_registration_number: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Customer NIF / tax number. Provide this OR customer_id to identify the customer. "
                "Use '999999990' for anonymous / final consumer."
            ),
        ),
    ] = None
    customer_id: Annotated[
        int | None,
        Field(
            default=None,
            description="Existing TOC Online customer ID. Use OR customer_tax_registration_number.",
        ),
    ] = None
    customer_business_name: Annotated[
        str | None,
        Field(
            default=None,
            description="Customer name (required if creating a new customer record).",
        ),
    ] = None
    customer_address_detail: Annotated[
        str | None,
        Field(
            default=None, description="Customer street address for the document header."
        ),
    ] = None
    customer_city: Annotated[
        str | None,
        Field(default=None, description="Customer city for the document header."),
    ] = None
    customer_postcode: Annotated[
        str | None,
        Field(
            default=None, description="Customer postal code for the document header."
        ),
    ] = None
    customer_country: Annotated[
        str | None,
        Field(
            default=None, description="Customer country ISO alpha-2 code (e.g. 'PT')."
        ),
    ] = None
    due_date: Annotated[
        str | None,
        Field(
            default=None,
            description="Payment due date in ISO 8601 format (YYYY-MM-DD).",
        ),
    ] = None
    finalize: Annotated[
        int | None,
        Field(
            default=None,
            description="Pass 1 to finalize the document immediately, 0 to keep as draft.",
        ),
    ] = None
    payment_mechanism: Annotated[
        str | None,
        Field(
            default=None,
            description="Payment mechanism code (e.g. 'MO' = cash, 'TB' = bank transfer).",
        ),
    ] = None
    notes: Annotated[
        str | None,
        Field(
            default=None, description="Document-level notes (printed on the document)."
        ),
    ] = None
    external_reference: Annotated[
        str | None,
        Field(default=None, description="External reference number or PO number."),
    ] = None
    currency_iso_code: Annotated[
        str | None,
        Field(default=None, description="ISO 4217 currency code (e.g. 'EUR', 'USD')."),
    ] = None
    currency_conversion_rate: Annotated[
        float | None,
        Field(
            default=None,
            description="Exchange rate to EUR when using a foreign currency.",
        ),
    ] = None
    operation_country: Annotated[
        str | None,
        Field(
            default=None,
            description="VAT operation country/region code (e.g. 'PT', 'PT-MA').",
        ),
    ] = None
    retention: Annotated[
        float | None,
        Field(
            default=None,
            description="Retention percentage to apply (e.g. 7.5 for IRS retention).",
        ),
    ] = None
    retention_type: Annotated[
        str | None,
        Field(default=None, description="Retention type: 'IRS' or 'IRC'."),
    ] = None
    apply_retention_when_paid: Annotated[
        bool | None,
        Field(
            default=None,
            description="If True, retention is only applied at receipt time; otherwise applied immediately.",
        ),
    ] = None
    settlement_expression: Annotated[
        str | None,
        Field(
            default=None,
            description="Header-level discount expression (e.g. '7.5' for 7.5% discount).",
        ),
    ] = None
    vat_included_prices: Annotated[
        bool | None,
        Field(
            default=None,
            description="Whether unit prices already include VAT.",
        ),
    ] = None
    document_series_id: Annotated[
        int | None,
        Field(
            default=None,
            description=(
                "ID of the document series to use. Use /api/commercial_document_series to list "
                "available series. Takes precedence over document_series_prefix."
            ),
        ),
    ] = None
    document_series_prefix: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Prefix of the document series to use (e.g. '2024'). Alternative to "
                "document_series_id when you know the prefix but not the ID."
            ),
        ),
    ] = None
    lines: Annotated[
        list[SalesDocumentLine] | None,
        Field(
            default=None, description="Document lines (products/services to include)."
        ),
    ] = None


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_sales_documents(
    ctx: Context,
    status: Annotated[
        str | None,
        Field(
            default=None,
            description="Filter by document status: '1' = finalized, '0' = draft. Omit for all.",
        ),
    ] = None,
    customer_id: Annotated[
        str | None,
        Field(
            default=None,
            description="Filter by customer ID (numeric string). Maps to filter[customer_id].",
        ),
    ] = None,
    date_from: Annotated[
        str | None,
        Field(
            default=None,
            description="Return documents on or after this date (YYYY-MM-DD). Maps to filter[date_from].",
        ),
    ] = None,
    date_to: Annotated[
        str | None,
        Field(
            default=None,
            description="Return documents on or before this date (YYYY-MM-DD). Maps to filter[date_to].",
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
    """Return sales documents for the current company.

    Pass status='1' to list finalized documents or status='0' for drafts.
    Use date_from / date_to to restrict by document date, and customer_id to
    filter by customer. Each item contains document id, type, date, totals,
    and customer info.
    """
    client = get_client(ctx)
    params: dict[str, str] = {}
    if status is not None:
        params["filter[status]"] = status
    if customer_id:
        params["filter[customer_id]"] = customer_id
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
            "/api/v1/commercial_sales_documents/", params=params
        )
    except TOCOnlineError as exc:
        await ctx.error(f"list_sales_documents failed: {exc}")
        raise ToolError(str(exc))

    data = response.get("data", [])
    if not isinstance(data, list):
        data = [data]

    items = [{"id": item.get("id"), **item.get("attributes", {})} for item in data]
    meta = response.get("meta", {})
    return {"data": items, "meta": meta}


@mcp.tool()
async def get_sales_document(
    ctx: Context,
    document_id: Annotated[str, Field(description="The TOC Online sales document ID.")],
) -> dict[str, Any]:
    """Return a single sales document by ID, including all attributes and line references."""
    client = get_client(ctx)
    validate_resource_id(document_id, "document_id")
    try:
        response = await client.get(f"/api/v1/commercial_sales_documents/{document_id}")
    except TOCOnlineError as exc:
        await ctx.error(f"get_sales_document({document_id}) failed: {exc}")
        raise ToolError(str(exc))

    item = response.get("data", {})
    return {"id": item.get("id"), **item.get("attributes", {})}


@write_tool
async def create_sales_document(
    ctx: Context,
    attributes: Annotated[
        SalesDocumentAttributes,
        Field(
            description=(
                "Sales document header and lines. Use the v1 endpoint to create the header "
                "and all lines atomically. Set finalize=1 to immediately finalize."
            )
        ),
    ],
) -> dict[str, Any]:
    """Create a new sales document (header + lines) in a single atomic call.

    This uses the v1 endpoint which supports creating the header and all lines together.
    Set ``finalize=1`` to finalize immediately. Returns the created document with its ID.

    To create a draft and add lines separately, set ``finalize=0`` and then call
    ``create_sales_document_line`` for each line, then ``finalize_sales_document``.
    """
    client = get_client(ctx)
    payload = attributes.model_dump(exclude_none=True)

    try:
        response = await client.post("/api/v1/commercial_sales_documents", json=payload)
    except TOCOnlineError as exc:
        await ctx.error(f"create_sales_document failed: {exc}")
        raise ToolError(str(exc))

    item = response.get("data", {})
    await ctx.info(f"Sales document created with id={item.get('id')}")
    return {"id": item.get("id"), **item.get("attributes", {})}


@write_tool
async def finalize_sales_document(
    ctx: Context,
    document_id: Annotated[
        str, Field(description="The TOC Online sales document ID to finalize.")
    ],
) -> dict[str, Any]:
    """Finalize a draft sales document (set status to 1).

    Once finalized, document content is locked and it can be sent or communicated to AT.
    Returns the updated document record.
    """
    client = get_client(ctx)
    validate_resource_id(document_id, "document_id")
    payload = {
        "data": {
            "type": "commercial_sales_documents",
            "id": document_id,
            "attributes": {"status": 1},
        }
    }
    try:
        response = await client.patch("/api/commercial_sales_documents", json=payload)
    except TOCOnlineError as exc:
        await ctx.error(f"finalize_sales_document({document_id}) failed: {exc}")
        raise ToolError(str(exc))

    item = response.get("data", {})
    await ctx.info(f"Sales document {document_id} finalized")
    return {"id": item.get("id"), **item.get("attributes", {})}


@write_tool
async def delete_sales_document(
    ctx: Context,
    document_id: Annotated[
        str, Field(description="The TOC Online sales document ID to delete.")
    ],
) -> dict[str, Any]:
    """Delete a draft sales document by ID.

    Only draft (non-finalized) documents can be deleted.
    Returns a confirmation meta object on success.
    """
    client = get_client(ctx)
    validate_resource_id(document_id, "document_id")
    try:
        response = await client.delete(f"/api/commercial_sales_documents/{document_id}")
    except TOCOnlineError as exc:
        await ctx.error(f"delete_sales_document({document_id}) failed: {exc}")
        raise ToolError(str(exc))

    await ctx.info(f"Sales document {document_id} deleted")
    return response.get("meta", {"result": "deleted"})


@mcp.tool()
async def get_sales_document_pdf_url(
    ctx: Context,
    document_id: Annotated[str, Field(description="The TOC Online sales document ID.")],
) -> dict[str, Any]:
    """Get a signed URL to download the PDF of a finalized sales document.

    Returns a url object containing scheme, host, port, and path fields that can
    be assembled into a full download URL.
    """
    client = get_client(ctx)
    validate_resource_id(document_id, "document_id")
    try:
        response = await client.get(
            f"/api/url_for_print/{document_id}",
            params={"filter[type]": "Document"},
        )
    except TOCOnlineError as exc:
        await ctx.error(f"get_sales_document_pdf_url({document_id}) failed: {exc}")
        raise ToolError(str(exc))

    item = response.get("data", {})
    attrs = item.get("attributes", {})
    url_obj = attrs.get("url", attrs)
    # Build a convenience full_url if all parts are present
    if isinstance(url_obj, dict) and url_obj.get("host"):
        scheme = url_obj.get("scheme", "https")
        host = url_obj.get("host", "")
        path = url_obj.get("path", "")
        port = url_obj.get("port", 443)
        full_url = f"{scheme}://{host}:{port}{path}"
        return {"id": item.get("id"), "full_url": full_url, **url_obj}
    return {"id": item.get("id"), **attrs}


@write_tool
async def send_sales_document_email(
    ctx: Context,
    document_id: Annotated[
        str, Field(description="The TOC Online sales document ID to email.")
    ],
    to_email: Annotated[str, Field(description="Recipient email address.")],
    from_email: Annotated[str, Field(description="Sender email address.")],
    from_name: Annotated[str, Field(description="Sender display name.")],
    subject: Annotated[str, Field(description="Email subject line.")],
) -> dict[str, Any]:
    """Send a finalized sales document by email.

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
                "type": "Document",
            },
        }
    }
    try:
        response = await client.patch("/api/email/document", json=payload)
    except TOCOnlineError as exc:
        await ctx.error(f"send_sales_document_email({document_id}) failed: {exc}")
        raise ToolError(str(exc))

    await ctx.info(f"Sales document {document_id} emailed to {to_email}")
    return response.get("meta", response.get("data", {"result": "sent"}))
