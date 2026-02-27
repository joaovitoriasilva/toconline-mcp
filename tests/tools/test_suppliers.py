"""Tests for toconline_mcp.tools.suppliers.

Covers list_suppliers, get_supplier, create_supplier, update_supplier,
and delete_supplier for happy paths, error propagation, and parameter
forwarding.
"""

from __future__ import annotations

import pytest

from mcp.server.fastmcp.exceptions import ToolError
from toconline_mcp.client import TOCOnlineError
from toconline_mcp.tools.suppliers import (
    SupplierAttributes,
    SupplierUpdateAttributes,
    create_supplier,
    delete_supplier,
    get_supplier,
    list_suppliers,
    update_supplier,
)

# ---------------------------------------------------------------------------
# list_suppliers
# ---------------------------------------------------------------------------


class TestListSuppliers:
    """Tests for the list_suppliers read tool."""

    async def test_returns_transformed_items(self, mock_ctx, mock_api_client):
        """Happy path: JSON:API response is flattened into {id, **attributes} items."""
        mock_api_client.get.return_value = {
            "data": [{"id": "10", "attributes": {"business_name": "Fornecedor SA"}}],
            "meta": {"total": 1},
        }
        result = await list_suppliers(mock_ctx)
        assert result["data"] == [{"id": "10", "business_name": "Fornecedor SA"}]
        assert result["meta"] == {"total": 1}

    async def test_returns_empty_data_when_no_suppliers(
        self, mock_ctx, mock_api_client
    ):
        """Empty data list is returned as an empty result set."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        result = await list_suppliers(mock_ctx)
        assert result == {"data": [], "meta": {}}

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client
    ):
        """TOCOnlineError is caught and re-raised as ToolError."""
        mock_api_client.get.side_effect = TOCOnlineError(
            [{"code": "503", "detail": "Service unavailable"}], 503
        )
        with pytest.raises(ToolError):
            await list_suppliers(mock_ctx)

    async def test_passes_business_name_filter(self, mock_ctx, mock_api_client):
        """business_name is forwarded as filter[business_name] query parameter."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_suppliers(mock_ctx, business_name="Forn")
        _, kwargs = mock_api_client.get.call_args
        assert kwargs["params"]["filter[business_name]"] == "Forn"

    async def test_passes_tax_registration_number_filter(
        self, mock_ctx, mock_api_client
    ):
        """tax_registration_number is forwarded as filter[tax_registration_number]."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_suppliers(mock_ctx, tax_registration_number="501234567")
        _, kwargs = mock_api_client.get.call_args
        assert kwargs["params"]["filter[tax_registration_number]"] == "501234567"

    async def test_passes_pagination_params(self, mock_ctx, mock_api_client):
        """page and per_page are forwarded as page[number] and page[size]."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_suppliers(mock_ctx, page=3, per_page=5)
        _, kwargs = mock_api_client.get.call_args
        assert kwargs["params"]["page[number]"] == "3"
        assert kwargs["params"]["page[size]"] == "5"

    async def test_calls_correct_endpoint(self, mock_ctx, mock_api_client):
        """GET /api/suppliers is the endpoint called."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_suppliers(mock_ctx)
        args, _ = mock_api_client.get.call_args
        assert args[0] == "/api/suppliers"

    async def test_list_suppliers_no_filters_sends_no_filter_params(
        self, mock_ctx, mock_api_client
    ) -> None:
        """With no filter args, no filter keys appear in the params dict."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_suppliers(mock_ctx)
        _, kwargs = mock_api_client.get.call_args
        params = kwargs.get("params", {})
        assert not any(k.startswith("filter[") for k in params)


# ---------------------------------------------------------------------------
# get_supplier
# ---------------------------------------------------------------------------


class TestGetSupplier:
    """Tests for the get_supplier read tool."""

    async def test_returns_flattened_supplier(self, mock_ctx, mock_api_client):
        """Happy path: data dict is flattened into {id, **attributes}."""
        mock_api_client.get.return_value = {
            "data": {
                "id": "55",
                "attributes": {"business_name": "Sup Lda", "website": "https://sup.pt"},
            }
        }
        result = await get_supplier(mock_ctx, supplier_id="55")
        assert result == {
            "id": "55",
            "business_name": "Sup Lda",
            "website": "https://sup.pt",
        }

    async def test_calls_correct_endpoint(self, mock_ctx, mock_api_client):
        """GET /api/suppliers/{id} is the endpoint called."""
        mock_api_client.get.return_value = {"data": {"id": "3", "attributes": {}}}
        await get_supplier(mock_ctx, supplier_id="3")
        args, _ = mock_api_client.get.call_args
        assert args[0] == "/api/suppliers/3"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client
    ):
        """TOCOnlineError is caught and re-raised as ToolError."""
        mock_api_client.get.side_effect = TOCOnlineError(
            [{"code": "404", "detail": "Not found"}], 404
        )
        with pytest.raises(ToolError):
            await get_supplier(mock_ctx, supplier_id="999")

    async def test_get_supplier_invalid_id_raises_tool_error(self, mock_ctx) -> None:
        """A non-numeric supplier_id raises ToolError before any API call."""
        with pytest.raises(ToolError):
            await get_supplier(mock_ctx, supplier_id="abc!")
        mock_ctx.request_context.lifespan_context["api_client"].get.assert_not_called()


# ---------------------------------------------------------------------------
# create_supplier
# ---------------------------------------------------------------------------


class TestCreateSupplier:
    """Tests for the create_supplier write tool."""

    async def test_returns_created_supplier(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """Happy path: newly created supplier dict is returned."""
        mock_api_client.post.return_value = {
            "data": {"id": "88", "attributes": {"business_name": "New Sup Lda"}}
        }
        attrs = SupplierAttributes(
            business_name="New Sup Lda", tax_registration_number="501234567"
        )
        result = await create_supplier(mock_ctx, attributes=attrs)
        assert result == {"id": "88", "business_name": "New Sup Lda"}

    async def test_posts_to_correct_endpoint(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """POST /api/suppliers is the endpoint called."""
        mock_api_client.post.return_value = {"data": {"id": "1", "attributes": {}}}
        attrs = SupplierAttributes(
            business_name="S", tax_registration_number="501234567"
        )
        await create_supplier(mock_ctx, attributes=attrs)
        args, _ = mock_api_client.post.call_args
        assert args[0] == "/api/suppliers"

    async def test_payload_type_is_suppliers(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """The JSON:API type in the payload is 'suppliers'."""
        mock_api_client.post.return_value = {"data": {"id": "1", "attributes": {}}}
        attrs = SupplierAttributes(
            business_name="S", tax_registration_number="501234567"
        )
        await create_supplier(mock_ctx, attributes=attrs)
        _, kwargs = mock_api_client.post.call_args
        assert kwargs["json"]["data"]["type"] == "suppliers"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """TOCOnlineError from a failed POST is re-raised as ToolError."""
        mock_api_client.post.side_effect = TOCOnlineError(
            [{"code": "403", "detail": "Duplicate NIF"}], 403
        )
        attrs = SupplierAttributes(
            business_name="Dup", tax_registration_number="501234567"
        )
        with pytest.raises(ToolError):
            await create_supplier(mock_ctx, attributes=attrs)


# ---------------------------------------------------------------------------
# update_supplier
# ---------------------------------------------------------------------------


class TestUpdateSupplier:
    """Tests for the update_supplier write tool."""

    async def test_returns_updated_supplier(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """Happy path: updated supplier attributes are returned."""
        mock_api_client.patch.return_value = {
            "data": {"id": "55", "attributes": {"website": "https://new.pt"}}
        }
        attrs = SupplierUpdateAttributes(website="https://new.pt")
        result = await update_supplier(mock_ctx, supplier_id="55", attributes=attrs)
        assert result["id"] == "55"
        assert result["website"] == "https://new.pt"

    async def test_patches_to_correct_endpoint(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """PATCH /api/suppliers is the endpoint called."""
        mock_api_client.patch.return_value = {"data": {"id": "1", "attributes": {}}}
        await update_supplier(
            mock_ctx,
            supplier_id="1",
            attributes=SupplierUpdateAttributes(business_name="Updated"),
        )
        args, _ = mock_api_client.patch.call_args
        assert args[0] == "/api/suppliers"

    async def test_payload_embeds_supplier_id(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """The supplier ID is embedded in the JSON:API payload."""
        mock_api_client.patch.return_value = {"data": {"id": "7", "attributes": {}}}
        await update_supplier(
            mock_ctx,
            supplier_id="7",
            attributes=SupplierUpdateAttributes(website="https://x.pt"),
        )
        _, kwargs = mock_api_client.patch.call_args
        assert kwargs["json"]["data"]["id"] == "7"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """TOCOnlineError from a failed PATCH is re-raised as ToolError."""
        mock_api_client.patch.side_effect = TOCOnlineError(
            [{"code": "422", "detail": "Invalid"}], 422
        )
        with pytest.raises(ToolError):
            await update_supplier(
                mock_ctx,
                supplier_id="1",
                attributes=SupplierUpdateAttributes(website="bad"),
            )

    async def test_update_supplier_invalid_id_raises_tool_error(
        self, mock_ctx, patch_settings
    ) -> None:
        """A non-numeric supplier_id raises ToolError before any API call."""
        with pytest.raises(ToolError):
            await update_supplier(
                mock_ctx,
                supplier_id="abc!",
                attributes=SupplierUpdateAttributes(website="https://x.pt"),
            )
        mock_ctx.request_context.lifespan_context[
            "api_client"
        ].patch.assert_not_called()


# ---------------------------------------------------------------------------
# delete_supplier
# ---------------------------------------------------------------------------


class TestDeleteSupplier:
    """Tests for the delete_supplier write tool."""

    async def test_returns_meta_on_success(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """Happy path: the meta confirmation dict is returned."""
        mock_api_client.delete.return_value = {"meta": {"result": "deleted"}}
        result = await delete_supplier(mock_ctx, supplier_id="55")
        assert result == {"result": "deleted"}

    async def test_calls_correct_endpoint(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """DELETE /api/suppliers/{id} is the endpoint called."""
        mock_api_client.delete.return_value = {"meta": {"result": "deleted"}}
        await delete_supplier(mock_ctx, supplier_id="55")
        args, _ = mock_api_client.delete.call_args
        assert args[0] == "/api/suppliers/55"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """TOCOnlineError from a failed DELETE is re-raised as ToolError."""
        mock_api_client.delete.side_effect = TOCOnlineError(
            [{"code": "403", "detail": "Has documents"}], 403
        )
        with pytest.raises(ToolError):
            await delete_supplier(mock_ctx, supplier_id="99")

    async def test_delete_supplier_invalid_id_raises_tool_error(
        self, mock_ctx, patch_settings
    ) -> None:
        """A non-numeric supplier_id raises ToolError before any API call."""
        with pytest.raises(ToolError):
            await delete_supplier(mock_ctx, supplier_id="abc!")
        mock_ctx.request_context.lifespan_context[
            "api_client"
        ].delete.assert_not_called()
