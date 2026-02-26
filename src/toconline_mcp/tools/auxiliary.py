"""MCP tools for TOC Online auxiliary/lookup resources.

These are read-only list endpoints that return reference data used when
constructing other resources (taxes, currencies, document series, etc.).

Endpoints covered:
  GET /api/taxes                          -> list_taxes
  GET /api/oss_taxes                      -> list_oss_taxes
  GET /api/countries                      -> list_countries
  GET /api/oss_countries                  -> list_oss_countries
  GET /api/currencies                     -> list_currencies
  GET /api/units_of_measure               -> list_units_of_measure
  GET /api/item_families                  -> list_item_families
  GET /api/expense_categories             -> list_expense_categories
  GET /api/commercial_document_series     -> list_document_series
  GET /api/bank_accounts                  -> list_bank_accounts
  GET /api/cash_accounts                  -> list_cash_accounts
  GET /api/tax_descriptors                -> list_tax_descriptors
"""

from __future__ import annotations

from typing import Annotated, Any

from mcp.server.fastmcp import Context
from pydantic import Field

from toconline_mcp.app import mcp
from toconline_mcp.tools._base import get_client, ToolError, TOCOnlineError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unwrap(response: dict[str, Any]) -> list[dict[str, Any]]:
    """Unwrap a JSON:API list response into a flat list of {id, **attributes}."""
    data = response.get("data", [])
    if not isinstance(data, list):
        data = [data]
    return [{"id": item.get("id"), **item.get("attributes", {})} for item in data]


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def list_taxes(
    ctx: Context,
    region: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Optional tax country region filter (maps to filter[tax_country_region]). "
                "E.g. 'PT' for mainland Portugal, 'PT-AC' for Azores, 'PT-MA' for Madeira."
            ),
        ),
    ] = None,
    code: Annotated[
        str | None,
        Field(
            default=None,
            description="Optional tax code filter (maps to filter[tax_code]). E.g. 'NOR', 'INT', 'RED', 'ISE'.",
        ),
    ] = None,
    tax_percentage: Annotated[
        str | None,
        Field(
            default=None,
            description="Filter by tax percentage value (e.g. '23', '6'). Maps to filter[tax_percentage].",
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
    """Return available VAT tax rates for the company's fiscal region.

    Each item contains the tax id, code, percentage, region, and description.
    Use the returned ``id`` as ``tax_id`` when creating document lines.
    Filter by ``region`` and/or ``code`` to narrow results.
    """
    client = get_client(ctx)
    params: dict[str, str] = {}
    if region:
        params["filter[tax_country_region]"] = region
    if code:
        params["filter[tax_code]"] = code
    if tax_percentage:
        params["filter[tax_percentage]"] = tax_percentage
    if page is not None:
        params["page[number]"] = str(page)
    if per_page is not None:
        params["page[size]"] = str(per_page)

    try:
        response = await client.get("/api/taxes", params=params)
    except TOCOnlineError as exc:
        await ctx.error(f"list_taxes failed: {exc}")
        raise ToolError(str(exc))

    items = _unwrap(response)
    meta = response.get("meta", {})
    return {"data": items, "meta": meta}


@mcp.tool()
async def list_countries(
    ctx: Context,
    iso_alpha_2: Annotated[
        str | None,
        Field(
            default=None,
            description="Filter by ISO alpha-2 country code (e.g. 'PT', 'ES', 'US'). Maps to filter[iso_alpha_2].",
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
    """Return all countries available in TOC Online.

    Each item contains the country id, ISO alpha-2 code, and name.
    Use the returned ``id`` as ``country_id`` in address and document attributes.
    Filter by ``iso_alpha_2`` to look up a specific country directly.
    """
    client = get_client(ctx)
    params: dict[str, str] = {}
    if iso_alpha_2:
        params["filter[iso_alpha_2]"] = iso_alpha_2
    if page is not None:
        params["page[number]"] = str(page)
    if per_page is not None:
        params["page[size]"] = str(per_page)
    try:
        response = await client.get("/api/countries", params=params)
    except TOCOnlineError as exc:
        await ctx.error(f"list_countries failed: {exc}")
        raise ToolError(str(exc))

    items = _unwrap(response)
    meta = response.get("meta", {})
    return {"data": items, "meta": meta}


@mcp.tool()
async def list_currencies(
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
    """Return all currencies supported by TOC Online.

    Each item contains the currency id, ISO code (e.g. 'EUR', 'USD'), and name.
    Use the returned ``id`` as ``currency_id`` in document attributes.
    """
    client = get_client(ctx)
    params: dict[str, str] = {}
    if page is not None:
        params["page[number]"] = str(page)
    if per_page is not None:
        params["page[size]"] = str(per_page)
    try:
        response = await client.get("/api/currencies", params=params)
    except TOCOnlineError as exc:
        await ctx.error(f"list_currencies failed: {exc}")
        raise ToolError(str(exc))

    items = _unwrap(response)
    meta = response.get("meta", {})
    return {"data": items, "meta": meta}


@mcp.tool()
async def list_units_of_measure(
    ctx: Context,
    unit_of_measure: Annotated[
        str | None,
        Field(
            default=None,
            description="Filter by unit name (e.g. 'horas', 'quilogramas', 'unidade'). Maps to filter[unit_of_measure].",
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
    """Return all units of measure defined in TOC Online.

    Each item contains the unit id, abbreviation (e.g. 'UN', 'KG', 'HR'), and name.
    Use the returned ``id`` as ``unit_of_measure_id`` in document line attributes.
    Filter by ``unit_of_measure`` abbreviation to look up a specific unit.
    """
    client = get_client(ctx)
    params: dict[str, str] = {}
    if unit_of_measure:
        params["filter[unit_of_measure]"] = unit_of_measure
    if page is not None:
        params["page[number]"] = str(page)
    if per_page is not None:
        params["page[size]"] = str(per_page)
    try:
        response = await client.get("/api/units_of_measure", params=params)
    except TOCOnlineError as exc:
        await ctx.error(f"list_units_of_measure failed: {exc}")
        raise ToolError(str(exc))

    items = _unwrap(response)
    meta = response.get("meta", {})
    return {"data": items, "meta": meta}


@mcp.tool()
async def list_item_families(
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
    """Return all product/service families (categories) defined in TOC Online.

    Each item contains the family id and name.
    Use the returned ``id`` as ``item_family_id`` when creating products or services.
    """
    client = get_client(ctx)
    params: dict[str, str] = {}
    if page is not None:
        params["page[number]"] = str(page)
    if per_page is not None:
        params["page[size]"] = str(per_page)
    try:
        response = await client.get("/api/item_families", params=params)
    except TOCOnlineError as exc:
        await ctx.error(f"list_item_families failed: {exc}")
        raise ToolError(str(exc))

    items = _unwrap(response)
    meta = response.get("meta", {})
    return {"data": items, "meta": meta}


@mcp.tool()
async def list_expense_categories(
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
    """Return all expense categories defined in TOC Online.

    Each item contains the category id and name.
    Use the returned ``id`` as ``expense_category_id`` in purchase document lines.
    """
    client = get_client(ctx)
    params: dict[str, str] = {}
    if page is not None:
        params["page[number]"] = str(page)
    if per_page is not None:
        params["page[size]"] = str(per_page)
    try:
        response = await client.get("/api/expense_categories", params=params)
    except TOCOnlineError as exc:
        await ctx.error(f"list_expense_categories failed: {exc}")
        raise ToolError(str(exc))

    items = _unwrap(response)
    meta = response.get("meta", {})
    return {"data": items, "meta": meta}


@mcp.tool()
async def list_document_series(
    ctx: Context,
    document_type: Annotated[
        str | None,
        Field(
            default=None,
            description=(
                "Optional document type filter (e.g. 'FT', 'FS', 'FF', 'RG'). "
                "Narrows results to series applicable to that document type."
            ),
        ),
    ] = None,
    prefix: Annotated[
        str | None,
        Field(
            default=None,
            description="Filter by series prefix (e.g. 'A', 'B'). Maps to filter[prefix].",
        ),
    ] = None,
    number: Annotated[
        str | None,
        Field(
            default=None,
            description="Filter by series sequence counter (e.g. '13'). This is NOT the year — use the `prefix` parameter to filter by year/prefix.",
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
    """Return all commercial document series available for the company.

    Each item contains the series id, name, document type, next sequence number,
    and fiscal year. Use the returned ``id`` as ``document_series_id`` when
    creating sales or purchase documents and receipts/payments.
    """
    client = get_client(ctx)
    params: dict[str, str] = {}
    if document_type:
        params["filter[document_type]"] = document_type
    if prefix:
        params["filter[prefix]"] = prefix
    if number:
        params["filter[number]"] = number
    if page is not None:
        params["page[number]"] = str(page)
    if per_page is not None:
        params["page[size]"] = str(per_page)

    try:
        response = await client.get("/api/commercial_document_series", params=params)
    except TOCOnlineError as exc:
        await ctx.error(f"list_document_series failed: {exc}")
        raise ToolError(str(exc))

    items = _unwrap(response)
    meta = response.get("meta", {})
    return {"data": items, "meta": meta}


@mcp.tool()
async def list_bank_accounts(
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
    """Return all bank accounts configured for the company.

    Each item contains the account id, IBAN, bank name, and currency.
    Use the returned ``id`` as ``bank_account_id`` in payment attributes.
    """
    client = get_client(ctx)
    params: dict[str, str] = {}
    if page is not None:
        params["page[number]"] = str(page)
    if per_page is not None:
        params["page[size]"] = str(per_page)
    try:
        response = await client.get("/api/bank_accounts", params=params)
    except TOCOnlineError as exc:
        await ctx.error(f"list_bank_accounts failed: {exc}")
        raise ToolError(str(exc))

    items = _unwrap(response)
    meta = response.get("meta", {})
    return {"data": items, "meta": meta}


@mcp.tool()
async def list_cash_accounts(
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
    """Return all cash accounts (caixas) configured for the company.

    Each item contains the account id, name, and current balance.
    Use the returned ``id`` as ``cash_account_id`` in receipt and payment attributes.
    """
    client = get_client(ctx)
    params: dict[str, str] = {}
    if page is not None:
        params["page[number]"] = str(page)
    if per_page is not None:
        params["page[size]"] = str(per_page)
    try:
        response = await client.get("/api/cash_accounts", params=params)
    except TOCOnlineError as exc:
        await ctx.error(f"list_cash_accounts failed: {exc}")
        raise ToolError(str(exc))

    items = _unwrap(response)
    meta = response.get("meta", {})
    return {"data": items, "meta": meta}


@mcp.tool()
async def list_oss_countries(
    ctx: Context,
) -> dict[str, Any]:
    """Return all EU OSS (One Stop Shop) countries supported by TOC Online.

    Each item contains the OSS country id, ISO alpha-2 and alpha-3 codes,
    default English name, and ``tax_country_region`` code.
    Use the returned data when configuring OSS document series or OSS tax rates.
    """
    client = get_client(ctx)
    try:
        response = await client.get("/api/oss_countries")
    except TOCOnlineError as exc:
        await ctx.error(f"list_oss_countries failed: {exc}")
        raise ToolError(str(exc))

    items = _unwrap(response)
    meta = response.get("meta", {})
    return {"data": items, "meta": meta}


@mcp.tool()
async def list_oss_taxes(
    ctx: Context,
) -> dict[str, Any]:
    """Return OSS (One Stop Shop) VAT rates for all EU countries.

    Each item contains the country ``tax_country_region`` code and three VAT
    bands: ``nor`` (normal), ``int`` (intermediate), and ``red`` (reduced).
    Each band is a list of strings in the format ``"<percentage>#<rank>"``
    (e.g. ``"23#1"`` means 23% rank-1 rate).
    Use this to look up the applicable OSS tax rate for a given EU country.
    """
    client = get_client(ctx)
    try:
        response = await client.get("/api/oss_taxes")
    except TOCOnlineError as exc:
        await ctx.error(f"list_oss_taxes failed: {exc}")
        raise ToolError(str(exc))

    items = _unwrap(response)
    meta = response.get("meta", {})
    return {"data": items, "meta": meta}


@mcp.tool()
async def list_tax_descriptors(
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
    """Return all tax descriptors (motivos de isenção / exemption reasons) in TOC Online.

    Each item contains the descriptor id, code, and description.
    Use the returned ``id`` as ``tax_descriptor_id`` on document lines where the
    item is VAT-exempt (e.g. ISE = Isento).
    """
    client = get_client(ctx)
    params: dict[str, str] = {}
    if page is not None:
        params["page[number]"] = str(page)
    if per_page is not None:
        params["page[size]"] = str(per_page)
    try:
        response = await client.get("/api/tax_descriptors", params=params)
    except TOCOnlineError as exc:
        await ctx.error(f"list_tax_descriptors failed: {exc}")
        raise ToolError(str(exc))

    items = _unwrap(response)
    meta = response.get("meta", {})
    return {"data": items, "meta": meta}
