"""Tests for toconline_mcp.tools.auxiliary.

Covers all twelve read-only auxiliary tools: list_taxes, list_oss_taxes,
list_countries, list_oss_countries, list_currencies, list_units_of_measure,
list_item_families, list_expense_categories, list_document_series,
list_bank_accounts, list_cash_accounts, and list_tax_descriptors.
"""

from __future__ import annotations

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from toconline_mcp.client import TOCOnlineError
from toconline_mcp.tools.auxiliary import (
    list_bank_accounts,
    list_cash_accounts,
    list_countries,
    list_currencies,
    list_document_series,
    list_expense_categories,
    list_item_families,
    list_oss_countries,
    list_oss_taxes,
    list_tax_descriptors,
    list_taxes,
    list_units_of_measure,
)

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _jsonapi_response(*items: dict) -> dict:
    """Build a minimal JSON:API list response for the given attribute dicts."""
    return {
        "data": [
            {"id": str(i + 1), "attributes": item} for i, item in enumerate(items)
        ],
        "meta": {},
    }


# ---------------------------------------------------------------------------
# list_taxes
# ---------------------------------------------------------------------------


class TestListTaxes:
    """Tests for the list_taxes auxiliary tool."""

    async def test_returns_tax_items(self, mock_ctx, mock_api_client):
        """Happy path: response data is unwrapped into a flat list inside a dict."""
        mock_api_client.get.return_value = _jsonapi_response(
            {"tax_code": "NOR", "tax_percentage": "23"}
        )
        result = await list_taxes(mock_ctx)
        assert result["data"][0]["tax_code"] == "NOR"

    async def test_calls_api_taxes_endpoint(self, mock_ctx, mock_api_client):
        """GET /api/taxes is the endpoint called."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_taxes(mock_ctx)
        args, _ = mock_api_client.get.call_args
        assert args[0] == "/api/taxes"

    async def test_passes_region_filter(self, mock_ctx, mock_api_client):
        """region is forwarded as filter[tax_country_region]."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_taxes(mock_ctx, region="PT")
        _, kwargs = mock_api_client.get.call_args
        assert kwargs["params"]["filter[tax_country_region]"] == "PT"

    async def test_passes_code_filter(self, mock_ctx, mock_api_client):
        """code is forwarded as filter[tax_code]."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_taxes(mock_ctx, code="NOR")
        _, kwargs = mock_api_client.get.call_args
        assert kwargs["params"]["filter[tax_code]"] == "NOR"

    async def test_passes_tax_percentage_filter(self, mock_ctx, mock_api_client):
        """tax_percentage is forwarded as filter[tax_percentage]."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_taxes(mock_ctx, tax_percentage="23")
        _, kwargs = mock_api_client.get.call_args
        assert kwargs["params"]["filter[tax_percentage]"] == "23"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client
    ):
        """TOCOnlineError is caught and re-raised as ToolError."""
        mock_api_client.get.side_effect = TOCOnlineError(
            [{"code": "500", "detail": "Server error"}], 500
        )
        with pytest.raises(ToolError):
            await list_taxes(mock_ctx)

    async def test_list_taxes_no_filters_sends_no_filter_params(
        self, mock_ctx, mock_api_client
    ) -> None:
        """With no filter args, no filter keys appear in the params dict."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_taxes(mock_ctx)
        _, kwargs = mock_api_client.get.call_args
        params = kwargs.get("params", {})
        assert not any(k.startswith("filter[") for k in params)


# ---------------------------------------------------------------------------
# list_oss_taxes
# ---------------------------------------------------------------------------


class TestListOssTaxes:
    """Tests for the list_oss_taxes auxiliary tool."""

    async def test_returns_oss_tax_items(self, mock_ctx, mock_api_client):
        """Happy path: OSS tax data is unwrapped and returned."""
        mock_api_client.get.return_value = _jsonapi_response(
            {"tax_country_region": "DE", "nor": ["19#1"]}
        )
        result = await list_oss_taxes(mock_ctx)
        assert len(result["data"]) == 1

    async def test_calls_api_oss_taxes_endpoint(self, mock_ctx, mock_api_client):
        """GET /api/oss_taxes is the endpoint called."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_oss_taxes(mock_ctx)
        args, _ = mock_api_client.get.call_args
        assert args[0] == "/api/oss_taxes"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client
    ):
        """TOCOnlineError is caught and re-raised as ToolError."""
        mock_api_client.get.side_effect = TOCOnlineError(
            [{"code": "503", "detail": "Down"}], 503
        )
        with pytest.raises(ToolError):
            await list_oss_taxes(mock_ctx)


# ---------------------------------------------------------------------------
# list_countries
# ---------------------------------------------------------------------------


class TestListCountries:
    """Tests for the list_countries auxiliary tool."""

    async def test_returns_country_items(self, mock_ctx, mock_api_client):
        """Happy path: countries are returned in a {data, meta} dict."""
        mock_api_client.get.return_value = _jsonapi_response(
            {"iso_alpha_2": "PT", "name": "Portugal"}
        )
        result = await list_countries(mock_ctx)
        assert result["data"][0]["iso_alpha_2"] == "PT"

    async def test_calls_api_countries_endpoint(self, mock_ctx, mock_api_client):
        """GET /api/countries is the endpoint called."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_countries(mock_ctx)
        args, _ = mock_api_client.get.call_args
        assert args[0] == "/api/countries"

    async def test_passes_iso_alpha_2_filter(self, mock_ctx, mock_api_client):
        """iso_alpha_2 is forwarded as filter[iso_alpha_2]."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_countries(mock_ctx, iso_alpha_2="ES")
        _, kwargs = mock_api_client.get.call_args
        assert kwargs["params"]["filter[iso_alpha_2]"] == "ES"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client
    ):
        """TOCOnlineError is caught and re-raised as ToolError."""
        mock_api_client.get.side_effect = TOCOnlineError(
            [{"code": "500", "detail": "Error"}], 500
        )
        with pytest.raises(ToolError):
            await list_countries(mock_ctx)

    async def test_list_countries_no_filters_sends_no_filter_params(
        self, mock_ctx, mock_api_client
    ) -> None:
        """With no filter args, no filter keys appear in the params dict."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_countries(mock_ctx)
        _, kwargs = mock_api_client.get.call_args
        params = kwargs.get("params", {})
        assert not any(k.startswith("filter[") for k in params)


# ---------------------------------------------------------------------------
# list_oss_countries
# ---------------------------------------------------------------------------


class TestListOssCountries:
    """Tests for the list_oss_countries auxiliary tool."""

    async def test_returns_oss_country_items(self, mock_ctx, mock_api_client):
        """Happy path: OSS countries are returned in a {data, meta} dict."""
        mock_api_client.get.return_value = _jsonapi_response(
            {"iso_alpha_2": "DE", "tax_country_region": "DE"}
        )
        result = await list_oss_countries(mock_ctx)
        assert len(result["data"]) == 1

    async def test_calls_api_oss_countries_endpoint(self, mock_ctx, mock_api_client):
        """GET /api/oss_countries is the endpoint called."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_oss_countries(mock_ctx)
        args, _ = mock_api_client.get.call_args
        assert args[0] == "/api/oss_countries"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client
    ):
        """TOCOnlineError is caught and re-raised as ToolError."""
        mock_api_client.get.side_effect = TOCOnlineError(
            [{"code": "500", "detail": "Error"}], 500
        )
        with pytest.raises(ToolError):
            await list_oss_countries(mock_ctx)


# ---------------------------------------------------------------------------
# list_currencies
# ---------------------------------------------------------------------------


class TestListCurrencies:
    """Tests for the list_currencies auxiliary tool."""

    async def test_returns_currency_items(self, mock_ctx, mock_api_client):
        """Happy path: currencies are returned in a {data, meta} dict."""
        mock_api_client.get.return_value = _jsonapi_response(
            {"iso_code": "EUR", "name": "Euro"}
        )
        result = await list_currencies(mock_ctx)
        assert result["data"][0]["iso_code"] == "EUR"

    async def test_calls_api_currencies_endpoint(self, mock_ctx, mock_api_client):
        """GET /api/currencies is the endpoint called."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_currencies(mock_ctx)
        args, _ = mock_api_client.get.call_args
        assert args[0] == "/api/currencies"

    async def test_passes_pagination_params(self, mock_ctx, mock_api_client):
        """page and per_page are forwarded as page[number] and page[size]."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_currencies(mock_ctx, page=1, per_page=50)
        _, kwargs = mock_api_client.get.call_args
        assert kwargs["params"]["page[number]"] == "1"
        assert kwargs["params"]["page[size]"] == "50"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client
    ):
        """TOCOnlineError is caught and re-raised as ToolError."""
        mock_api_client.get.side_effect = TOCOnlineError(
            [{"code": "500", "detail": "Error"}], 500
        )
        with pytest.raises(ToolError):
            await list_currencies(mock_ctx)


# ---------------------------------------------------------------------------
# list_units_of_measure
# ---------------------------------------------------------------------------


class TestListUnitsOfMeasure:
    """Tests for the list_units_of_measure auxiliary tool."""

    async def test_returns_unit_items(self, mock_ctx, mock_api_client):
        """Happy path: units of measure are returned in a {data, meta} dict."""
        mock_api_client.get.return_value = _jsonapi_response(
            {"unit_of_measure": "UN", "description": "Unidade"}
        )
        result = await list_units_of_measure(mock_ctx)
        assert result["data"][0]["unit_of_measure"] == "UN"

    async def test_calls_api_units_endpoint(self, mock_ctx, mock_api_client):
        """GET /api/units_of_measure is the endpoint called."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_units_of_measure(mock_ctx)
        args, _ = mock_api_client.get.call_args
        assert args[0] == "/api/units_of_measure"

    async def test_passes_unit_of_measure_filter(self, mock_ctx, mock_api_client):
        """unit_of_measure is forwarded as filter[unit_of_measure]."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_units_of_measure(mock_ctx, unit_of_measure="horas")
        _, kwargs = mock_api_client.get.call_args
        assert kwargs["params"]["filter[unit_of_measure]"] == "horas"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client
    ):
        """TOCOnlineError is caught and re-raised as ToolError."""
        mock_api_client.get.side_effect = TOCOnlineError(
            [{"code": "500", "detail": "Error"}], 500
        )
        with pytest.raises(ToolError):
            await list_units_of_measure(mock_ctx)


# ---------------------------------------------------------------------------
# list_item_families
# ---------------------------------------------------------------------------


class TestListItemFamilies:
    """Tests for the list_item_families auxiliary tool."""

    async def test_returns_family_items(self, mock_ctx, mock_api_client):
        """Happy path: item families are returned in a {data, meta} dict."""
        mock_api_client.get.return_value = _jsonapi_response({"name": "Informática"})
        result = await list_item_families(mock_ctx)
        assert result["data"][0]["name"] == "Informática"

    async def test_calls_api_item_families_endpoint(self, mock_ctx, mock_api_client):
        """GET /api/item_families is the endpoint called."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_item_families(mock_ctx)
        args, _ = mock_api_client.get.call_args
        assert args[0] == "/api/item_families"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client
    ):
        """TOCOnlineError is caught and re-raised as ToolError."""
        mock_api_client.get.side_effect = TOCOnlineError(
            [{"code": "500", "detail": "Error"}], 500
        )
        with pytest.raises(ToolError):
            await list_item_families(mock_ctx)


# ---------------------------------------------------------------------------
# list_expense_categories
# ---------------------------------------------------------------------------


class TestListExpenseCategories:
    """Tests for the list_expense_categories auxiliary tool."""

    async def test_returns_expense_category_items(self, mock_ctx, mock_api_client):
        """Happy path: expense categories are returned in a {data, meta} dict."""
        mock_api_client.get.return_value = _jsonapi_response({"name": "Viagens"})
        result = await list_expense_categories(mock_ctx)
        assert result["data"][0]["name"] == "Viagens"

    async def test_calls_api_expense_categories_endpoint(
        self, mock_ctx, mock_api_client
    ):
        """GET /api/expense_categories is the endpoint called."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_expense_categories(mock_ctx)
        args, _ = mock_api_client.get.call_args
        assert args[0] == "/api/expense_categories"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client
    ):
        """TOCOnlineError is caught and re-raised as ToolError."""
        mock_api_client.get.side_effect = TOCOnlineError(
            [{"code": "500", "detail": "Error"}], 500
        )
        with pytest.raises(ToolError):
            await list_expense_categories(mock_ctx)


# ---------------------------------------------------------------------------
# list_document_series
# ---------------------------------------------------------------------------


class TestListDocumentSeries:
    """Tests for the list_document_series auxiliary tool."""

    async def test_returns_series_items(self, mock_ctx, mock_api_client):
        """Happy path: document series are returned in a {data, meta} dict."""
        mock_api_client.get.return_value = _jsonapi_response(
            {"prefix": "A", "document_type": "FT"}
        )
        result = await list_document_series(mock_ctx)
        assert result["data"][0]["prefix"] == "A"

    async def test_calls_api_commercial_document_series_endpoint(
        self, mock_ctx, mock_api_client
    ):
        """GET /api/commercial_document_series is the endpoint called."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_document_series(mock_ctx)
        args, _ = mock_api_client.get.call_args
        assert args[0] == "/api/commercial_document_series"

    async def test_passes_document_type_filter(self, mock_ctx, mock_api_client):
        """document_type is forwarded as filter[document_type]."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_document_series(mock_ctx, document_type="FT")
        _, kwargs = mock_api_client.get.call_args
        assert kwargs["params"]["filter[document_type]"] == "FT"

    async def test_passes_prefix_filter(self, mock_ctx, mock_api_client):
        """prefix is forwarded as filter[prefix]."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_document_series(mock_ctx, prefix="2025")
        _, kwargs = mock_api_client.get.call_args
        assert kwargs["params"]["filter[prefix]"] == "2025"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client
    ):
        """TOCOnlineError is caught and re-raised as ToolError."""
        mock_api_client.get.side_effect = TOCOnlineError(
            [{"code": "500", "detail": "Error"}], 500
        )
        with pytest.raises(ToolError):
            await list_document_series(mock_ctx)


# ---------------------------------------------------------------------------
# list_bank_accounts
# ---------------------------------------------------------------------------


class TestListBankAccounts:
    """Tests for the list_bank_accounts auxiliary tool."""

    async def test_returns_bank_account_items(self, mock_ctx, mock_api_client):
        """Happy path: bank accounts are returned in a {data, meta} dict."""
        mock_api_client.get.return_value = _jsonapi_response(
            {"iban": "PT50003500000000000000000", "bank_name": "Caixa"}
        )
        result = await list_bank_accounts(mock_ctx)
        assert result["data"][0]["iban"] == "PT50003500000000000000000"

    async def test_calls_api_bank_accounts_endpoint(self, mock_ctx, mock_api_client):
        """GET /api/bank_accounts is the endpoint called."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_bank_accounts(mock_ctx)
        args, _ = mock_api_client.get.call_args
        assert args[0] == "/api/bank_accounts"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client
    ):
        """TOCOnlineError is caught and re-raised as ToolError."""
        mock_api_client.get.side_effect = TOCOnlineError(
            [{"code": "500", "detail": "Error"}], 500
        )
        with pytest.raises(ToolError):
            await list_bank_accounts(mock_ctx)


# ---------------------------------------------------------------------------
# list_cash_accounts
# ---------------------------------------------------------------------------


class TestListCashAccounts:
    """Tests for the list_cash_accounts auxiliary tool."""

    async def test_returns_cash_account_items(self, mock_ctx, mock_api_client):
        """Happy path: cash accounts are returned in a {data, meta} dict."""
        mock_api_client.get.return_value = _jsonapi_response(
            {"name": "Caixa Principal", "balance": "500.00"}
        )
        result = await list_cash_accounts(mock_ctx)
        assert result["data"][0]["name"] == "Caixa Principal"

    async def test_calls_api_cash_accounts_endpoint(self, mock_ctx, mock_api_client):
        """GET /api/cash_accounts is the endpoint called."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_cash_accounts(mock_ctx)
        args, _ = mock_api_client.get.call_args
        assert args[0] == "/api/cash_accounts"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client
    ):
        """TOCOnlineError is caught and re-raised as ToolError."""
        mock_api_client.get.side_effect = TOCOnlineError(
            [{"code": "500", "detail": "Error"}], 500
        )
        with pytest.raises(ToolError):
            await list_cash_accounts(mock_ctx)


# ---------------------------------------------------------------------------
# list_tax_descriptors
# ---------------------------------------------------------------------------


class TestListTaxDescriptors:
    """Tests for the list_tax_descriptors auxiliary tool."""

    async def test_returns_tax_descriptor_items(self, mock_ctx, mock_api_client):
        """Happy path: tax descriptors are returned in a {data, meta} dict."""
        mock_api_client.get.return_value = _jsonapi_response(
            {"code": "M01", "description": "Isento artigo 16.º"}
        )
        result = await list_tax_descriptors(mock_ctx)
        assert result["data"][0]["code"] == "M01"

    async def test_calls_api_tax_descriptors_endpoint(self, mock_ctx, mock_api_client):
        """GET /api/tax_descriptors is the endpoint called."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_tax_descriptors(mock_ctx)
        args, _ = mock_api_client.get.call_args
        assert args[0] == "/api/tax_descriptors"

    async def test_passes_pagination_params(self, mock_ctx, mock_api_client):
        """page and per_page are forwarded as page[number] and page[size]."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_tax_descriptors(mock_ctx, page=2, per_page=5)
        _, kwargs = mock_api_client.get.call_args
        assert kwargs["params"]["page[number]"] == "2"
        assert kwargs["params"]["page[size]"] == "5"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client
    ):
        """TOCOnlineError is caught and re-raised as ToolError."""
        mock_api_client.get.side_effect = TOCOnlineError(
            [{"code": "500", "detail": "Error"}], 500
        )
        with pytest.raises(ToolError):
            await list_tax_descriptors(mock_ctx)
