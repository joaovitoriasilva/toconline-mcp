"""Tests for toconline_mcp.tools.purchase_documents.

Covers list_purchase_documents, get_purchase_document, create_purchase_document,
finalize_purchase_document, and delete_purchase_document for happy paths,
error propagation, and API path verification.
"""

from __future__ import annotations

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from toconline_mcp.client import TOCOnlineError
from toconline_mcp.tools.purchase_documents import (
    PurchaseDocumentAttributes,
    create_purchase_document,
    delete_purchase_document,
    finalize_purchase_document,
    get_purchase_document,
    list_purchase_documents,
)

# ---------------------------------------------------------------------------
# list_purchase_documents
# ---------------------------------------------------------------------------


class TestListPurchaseDocuments:
    """Tests for the list_purchase_documents read tool."""

    async def test_returns_transformed_items(self, mock_ctx, mock_api_client):
        """Happy path: JSON:API response is flattened into {id, **attributes} items."""
        mock_api_client.get.return_value = {
            "data": [
                {
                    "id": "200",
                    "attributes": {"document_type": "FC", "date": "2025-02-01"},
                }
            ],
            "meta": {"total": 1},
        }
        result = await list_purchase_documents(mock_ctx)
        assert result["data"][0] == {
            "id": "200",
            "document_type": "FC",
            "date": "2025-02-01",
        }

    async def test_calls_correct_endpoint(self, mock_ctx, mock_api_client):
        """GET /api/v1/commercial_purchases_documents/ is the endpoint called."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_purchase_documents(mock_ctx)
        args, _ = mock_api_client.get.call_args
        assert args[0] == "/api/v1/commercial_purchases_documents/"

    async def test_passes_status_filter(self, mock_ctx, mock_api_client):
        """status is forwarded as filter[status]."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_purchase_documents(mock_ctx, status="1")
        _, kwargs = mock_api_client.get.call_args
        assert kwargs["params"]["filter[status]"] == "1"

    async def test_passes_supplier_id_filter(self, mock_ctx, mock_api_client):
        """supplier_id is forwarded as filter[supplier_id]."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_purchase_documents(mock_ctx, supplier_id="55")
        _, kwargs = mock_api_client.get.call_args
        assert kwargs["params"]["filter[supplier_id]"] == "55"

    async def test_passes_supplier_tax_number_filter(self, mock_ctx, mock_api_client):
        """supplier_tax_registration_number is forwarded as the correct filter key."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_purchase_documents(
            mock_ctx, supplier_tax_registration_number="501234567"
        )
        _, kwargs = mock_api_client.get.call_args
        assert (
            kwargs["params"]["filter[supplier_tax_registration_number]"] == "501234567"
        )

    async def test_passes_date_range_filters(self, mock_ctx, mock_api_client):
        """date_from and date_to are forwarded as their respective filter params."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_purchase_documents(
            mock_ctx, date_from="2025-01-01", date_to="2025-12-31"
        )
        _, kwargs = mock_api_client.get.call_args
        assert kwargs["params"]["filter[date_from]"] == "2025-01-01"
        assert kwargs["params"]["filter[date_to]"] == "2025-12-31"

    async def test_passes_pagination_params(self, mock_ctx, mock_api_client):
        """page and per_page are forwarded as page[number] and page[size]."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_purchase_documents(mock_ctx, page=1, per_page=15)
        _, kwargs = mock_api_client.get.call_args
        assert kwargs["params"]["page[number]"] == "1"
        assert kwargs["params"]["page[size]"] == "15"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client
    ):
        """TOCOnlineError is caught and re-raised as ToolError."""
        mock_api_client.get.side_effect = TOCOnlineError(
            [{"code": "500", "detail": "Server error"}], 500
        )
        with pytest.raises(ToolError):
            await list_purchase_documents(mock_ctx)

    async def test_list_purchase_documents_no_filters_sends_no_filter_params(
        self, mock_ctx, mock_api_client
    ) -> None:
        """With no filter args, no filter keys appear in the params dict."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_purchase_documents(mock_ctx)
        _, kwargs = mock_api_client.get.call_args
        params = kwargs.get("params", {})
        assert not any(k.startswith("filter[") for k in params)


# ---------------------------------------------------------------------------
# get_purchase_document
# ---------------------------------------------------------------------------


class TestGetPurchaseDocument:
    """Tests for the get_purchase_document read tool."""

    async def test_returns_flattened_document(self, mock_ctx, mock_api_client):
        """Happy path: data dict is flattened into {id, **attributes}."""
        mock_api_client.get.return_value = {
            "data": {
                "id": "200",
                "attributes": {"document_type": "FC", "supplier_id": "55"},
            }
        }
        result = await get_purchase_document(mock_ctx, document_id="200")
        assert result == {
            "id": "200",
            "document_type": "FC",
            "supplier_id": "55",
        }

    async def test_calls_correct_endpoint(self, mock_ctx, mock_api_client):
        """GET /api/commercial_purchases_documents/{id} is the endpoint called."""
        mock_api_client.get.return_value = {"data": {"id": "200", "attributes": {}}}
        await get_purchase_document(mock_ctx, document_id="200")
        args, _ = mock_api_client.get.call_args
        assert args[0] == "/api/commercial_purchases_documents/200"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client
    ):
        """TOCOnlineError is caught and re-raised as ToolError."""
        mock_api_client.get.side_effect = TOCOnlineError(
            [{"code": "404", "detail": "Not found"}], 404
        )
        with pytest.raises(ToolError):
            await get_purchase_document(mock_ctx, document_id="999")

    async def test_get_purchase_document_invalid_id_raises_tool_error(
        self, mock_ctx
    ) -> None:
        """A non-numeric document_id raises ToolError before any API call."""
        with pytest.raises(ToolError):
            await get_purchase_document(mock_ctx, document_id="abc!")
        mock_ctx.request_context.lifespan_context["api_client"].get.assert_not_called()


# ---------------------------------------------------------------------------
# create_purchase_document
# ---------------------------------------------------------------------------


class TestCreatePurchaseDocument:
    """Tests for the create_purchase_document write tool."""

    def _minimal_attrs(self) -> PurchaseDocumentAttributes:
        """Return minimal valid PurchaseDocumentAttributes for testing."""
        return PurchaseDocumentAttributes(
            document_type="FC",
            document_series_id=1,
            date="2025-02-10",
            supplier_id=55,
        )

    async def test_returns_created_document(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """Happy path: newly created purchase document is returned."""
        mock_api_client.post.return_value = {
            "data": {
                "id": "300",
                "attributes": {"document_type": "FC", "date": "2025-02-10"},
            }
        }
        result = await create_purchase_document(
            mock_ctx, attributes=self._minimal_attrs()
        )
        assert result["id"] == "300"
        assert result["document_type"] == "FC"

    async def test_posts_to_v1_endpoint(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """POST /api/v1/commercial_purchases_documents is the endpoint called."""
        mock_api_client.post.return_value = {"data": {"id": "1", "attributes": {}}}
        await create_purchase_document(mock_ctx, attributes=self._minimal_attrs())
        args, _ = mock_api_client.post.call_args
        assert args[0] == "/api/v1/commercial_purchases_documents"

    async def test_sends_flat_payload(self, mock_ctx, mock_api_client, patch_settings):
        """The POST payload is a flat JSON body (no JSON:API wrapper)."""
        mock_api_client.post.return_value = {"data": {"id": "1", "attributes": {}}}
        await create_purchase_document(mock_ctx, attributes=self._minimal_attrs())
        _, kwargs = mock_api_client.post.call_args
        assert "document_type" in kwargs["json"]
        assert kwargs["json"]["document_type"] == "FC"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """TOCOnlineError from a failed POST is re-raised as ToolError."""
        mock_api_client.post.side_effect = TOCOnlineError(
            [{"code": "422", "detail": "Invalid supplier"}], 422
        )
        with pytest.raises(ToolError):
            await create_purchase_document(mock_ctx, attributes=self._minimal_attrs())


# ---------------------------------------------------------------------------
# finalize_purchase_document
# ---------------------------------------------------------------------------


class TestFinalizePurchaseDocument:
    """Tests for the finalize_purchase_document write tool."""

    async def test_returns_response_on_success(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """Happy path: the API response (flat) is returned directly."""
        mock_api_client.patch.return_value = {"status": 1, "id": "200"}
        result = await finalize_purchase_document(mock_ctx, document_id="200")
        assert result == {"status": 1, "id": "200"}

    async def test_patches_to_v1_finalize_endpoint(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """PATCH /api/v1/commercial_purchases_documents/{id}/finalize is called."""
        mock_api_client.patch.return_value = {}
        await finalize_purchase_document(mock_ctx, document_id="200")
        args, _ = mock_api_client.patch.call_args
        assert args[0] == "/api/v1/commercial_purchases_documents/200/finalize"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """TOCOnlineError from a failed PATCH is re-raised as ToolError."""
        mock_api_client.patch.side_effect = TOCOnlineError(
            [{"code": "422", "detail": "Already finalized"}], 422
        )
        with pytest.raises(ToolError):
            await finalize_purchase_document(mock_ctx, document_id="200")

    async def test_finalize_purchase_document_invalid_id_raises_tool_error(
        self, mock_ctx, patch_settings
    ) -> None:
        """A non-numeric document_id raises ToolError before any API call."""
        with pytest.raises(ToolError):
            await finalize_purchase_document(mock_ctx, document_id="abc!")
        mock_ctx.request_context.lifespan_context[
            "api_client"
        ].patch.assert_not_called()


# ---------------------------------------------------------------------------
# delete_purchase_document
# ---------------------------------------------------------------------------


class TestDeletePurchaseDocument:
    """Tests for the delete_purchase_document write tool."""

    async def test_returns_meta_on_success(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """Happy path: the meta confirmation dict is returned."""
        mock_api_client.delete.return_value = {"meta": {"result": "deleted"}}
        result = await delete_purchase_document(mock_ctx, document_id="200")
        assert result == {"result": "deleted"}

    async def test_calls_correct_endpoint(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """DELETE /api/commercial_purchases_documents/{id} is the endpoint called."""
        mock_api_client.delete.return_value = {"meta": {"result": "deleted"}}
        await delete_purchase_document(mock_ctx, document_id="200")
        args, _ = mock_api_client.delete.call_args
        assert args[0] == "/api/commercial_purchases_documents/200"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """TOCOnlineError from a failed DELETE is re-raised as ToolError."""
        mock_api_client.delete.side_effect = TOCOnlineError(
            [{"code": "403", "detail": "Finalized — cannot delete"}], 403
        )
        with pytest.raises(ToolError):
            await delete_purchase_document(mock_ctx, document_id="200")

    async def test_delete_purchase_document_invalid_id_raises_tool_error(
        self, mock_ctx, patch_settings
    ) -> None:
        """A non-numeric document_id raises ToolError before any API call."""
        with pytest.raises(ToolError):
            await delete_purchase_document(mock_ctx, document_id="abc!")
        mock_ctx.request_context.lifespan_context[
            "api_client"
        ].delete.assert_not_called()
