"""Tests for toconline_mcp.tools.sales_receipts.

Covers list_sales_receipts, get_sales_receipt, create_sales_receipt, and
delete_sales_receipt for happy paths, error propagation, and API path
verification.
"""

from __future__ import annotations

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from toconline_mcp.client import TOCOnlineError
from toconline_mcp.tools.sales_receipts import (
    SalesReceiptAttributes,
    create_sales_receipt,
    delete_sales_receipt,
    get_sales_receipt,
    list_sales_receipts,
)

# ---------------------------------------------------------------------------
# list_sales_receipts
# ---------------------------------------------------------------------------


class TestListSalesReceipts:
    """Tests for the list_sales_receipts read tool."""

    async def test_returns_transformed_items(self, mock_ctx, mock_api_client):
        """Happy path: JSON:API response is flattened into {id, **attributes} items."""
        mock_api_client.get.return_value = {
            "data": [
                {
                    "id": "50",
                    "attributes": {"date": "2025-01-10", "gross_total": "500.00"},
                }
            ],
            "meta": {"total": 1},
        }
        result = await list_sales_receipts(mock_ctx)
        assert result["data"][0] == {
            "id": "50",
            "date": "2025-01-10",
            "gross_total": "500.00",
        }

    async def test_calls_correct_endpoint(self, mock_ctx, mock_api_client):
        """GET /api/v1/commercial_sales_receipts is the endpoint called."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_sales_receipts(mock_ctx)
        args, _ = mock_api_client.get.call_args
        assert args[0] == "/api/v1/commercial_sales_receipts"

    async def test_passes_document_no_filter(self, mock_ctx, mock_api_client):
        """document_no is forwarded as filter[document_no]."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_sales_receipts(mock_ctx, document_no="RG 2025/1")
        _, kwargs = mock_api_client.get.call_args
        assert kwargs["params"]["filter[document_no]"] == "RG 2025/1"

    async def test_passes_pagination_params(self, mock_ctx, mock_api_client):
        """page and per_page are forwarded as page[number] and page[size]."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_sales_receipts(mock_ctx, page=1, per_page=20)
        _, kwargs = mock_api_client.get.call_args
        assert kwargs["params"]["page[number]"] == "1"
        assert kwargs["params"]["page[size]"] == "20"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client
    ):
        """TOCOnlineError is caught and re-raised as ToolError."""
        mock_api_client.get.side_effect = TOCOnlineError(
            [{"code": "500", "detail": "Server error"}], 500
        )
        with pytest.raises(ToolError):
            await list_sales_receipts(mock_ctx)

    async def test_list_sales_receipts_no_filters_sends_no_filter_params(
        self, mock_ctx, mock_api_client
    ) -> None:
        """With no filter args, no filter keys appear in the params dict."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_sales_receipts(mock_ctx)
        _, kwargs = mock_api_client.get.call_args
        params = kwargs.get("params", {})
        assert not any(k.startswith("filter[") for k in params)


# ---------------------------------------------------------------------------
# get_sales_receipt
# ---------------------------------------------------------------------------


class TestGetSalesReceipt:
    """Tests for the get_sales_receipt read tool."""

    async def test_returns_flattened_receipt(self, mock_ctx, mock_api_client):
        """Happy path: data dict is flattened into {id, **attributes}."""
        mock_api_client.get.return_value = {
            "data": {
                "id": "50",
                "attributes": {"date": "2025-01-10", "gross_total": "500.00"},
            }
        }
        result = await get_sales_receipt(mock_ctx, receipt_id="50")
        assert result == {"id": "50", "date": "2025-01-10", "gross_total": "500.00"}

    async def test_calls_correct_endpoint(self, mock_ctx, mock_api_client):
        """GET /api/v1/commercial_sales_receipts/{id} is the endpoint called."""
        mock_api_client.get.return_value = {"data": {"id": "50", "attributes": {}}}
        await get_sales_receipt(mock_ctx, receipt_id="50")
        args, _ = mock_api_client.get.call_args
        assert args[0] == "/api/v1/commercial_sales_receipts/50"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client
    ):
        """TOCOnlineError is caught and re-raised as ToolError."""
        mock_api_client.get.side_effect = TOCOnlineError(
            [{"code": "404", "detail": "Not found"}], 404
        )
        with pytest.raises(ToolError):
            await get_sales_receipt(mock_ctx, receipt_id="999")

    async def test_get_sales_receipt_invalid_id_raises_tool_error(
        self, mock_ctx
    ) -> None:
        """A non-numeric receipt_id raises ToolError before any API call."""
        with pytest.raises(ToolError):
            await get_sales_receipt(mock_ctx, receipt_id="abc!")
        mock_ctx.request_context.lifespan_context["api_client"].get.assert_not_called()


# ---------------------------------------------------------------------------
# create_sales_receipt
# ---------------------------------------------------------------------------


class TestCreateSalesReceipt:
    """Tests for the create_sales_receipt write tool."""

    async def test_returns_created_receipt(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """Happy path: newly created sales receipt is returned with its assigned id."""
        mock_api_client.post.return_value = {
            "data": {
                "id": "75",
                "attributes": {"date": "2025-02-01", "gross_total": 300.0},
            }
        }
        attrs = SalesReceiptAttributes(
            date="2025-02-01",
            gross_total=300.0,
            net_total=243.9,
            payment_mechanism="TB",
        )
        result = await create_sales_receipt(mock_ctx, attributes=attrs)
        assert result["id"] == "75"

    async def test_posts_to_v1_endpoint(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """POST /api/v1/commercial_sales_receipts is the endpoint called."""
        mock_api_client.post.return_value = {"data": {"id": "1", "attributes": {}}}
        attrs = SalesReceiptAttributes(
            date="2025-01-01",
            gross_total=100.0,
            net_total=81.3,
            payment_mechanism="MO",
        )
        await create_sales_receipt(mock_ctx, attributes=attrs)
        args, _ = mock_api_client.post.call_args
        assert args[0] == "/api/v1/commercial_sales_receipts"

    async def test_sends_flat_payload(self, mock_ctx, mock_api_client, patch_settings):
        """The POST payload is a flat JSON body (no JSON:API data wrapper)."""
        mock_api_client.post.return_value = {"data": {"id": "1", "attributes": {}}}
        attrs = SalesReceiptAttributes(
            date="2025-01-01",
            gross_total=100.0,
            net_total=81.3,
            payment_mechanism="MO",
        )
        await create_sales_receipt(mock_ctx, attributes=attrs)
        _, kwargs = mock_api_client.post.call_args
        # Flat payload — not wrapped under {"data": ...}
        assert "date" in kwargs["json"]
        assert kwargs["json"]["payment_mechanism"] == "MO"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """TOCOnlineError from a failed POST is re-raised as ToolError."""
        mock_api_client.post.side_effect = TOCOnlineError(
            [{"code": "422", "detail": "Invalid payment mechanism"}], 422
        )
        attrs = SalesReceiptAttributes(
            date="2025-01-01",
            gross_total=100.0,
            net_total=81.3,
            payment_mechanism="XX",
        )
        with pytest.raises(ToolError):
            await create_sales_receipt(mock_ctx, attributes=attrs)


# ---------------------------------------------------------------------------
# delete_sales_receipt
# ---------------------------------------------------------------------------


class TestDeleteSalesReceipt:
    """Tests for the delete_sales_receipt write tool."""

    async def test_returns_meta_on_success(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """Happy path: the meta confirmation dict is returned."""
        mock_api_client.delete.return_value = {"meta": {"result": "deleted"}}
        result = await delete_sales_receipt(mock_ctx, receipt_id="75")
        assert result == {"result": "deleted"}

    async def test_calls_correct_endpoint(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """DELETE /api/v1/commercial_sales_receipts/{id} is the endpoint called."""
        mock_api_client.delete.return_value = {"meta": {"result": "deleted"}}
        await delete_sales_receipt(mock_ctx, receipt_id="75")
        args, _ = mock_api_client.delete.call_args
        assert args[0] == "/api/v1/commercial_sales_receipts/75"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """TOCOnlineError from a failed DELETE is re-raised as ToolError."""
        mock_api_client.delete.side_effect = TOCOnlineError(
            [{"code": "403", "detail": "Finalized — cannot delete"}], 403
        )
        with pytest.raises(ToolError):
            await delete_sales_receipt(mock_ctx, receipt_id="75")

    async def test_delete_sales_receipt_invalid_id_raises_tool_error(
        self, mock_ctx, patch_settings
    ) -> None:
        """A non-numeric receipt_id raises ToolError before any API call."""
        with pytest.raises(ToolError):
            await delete_sales_receipt(mock_ctx, receipt_id="abc!")
        mock_ctx.request_context.lifespan_context[
            "api_client"
        ].delete.assert_not_called()
