"""Tests for toconline_mcp.tools.products.

Covers list_products, create_product, update_product, and delete_product
for happy paths, error propagation, and API path verification.
"""

from __future__ import annotations

import pytest

from mcp.server.fastmcp.exceptions import ToolError
from toconline_mcp.client import TOCOnlineError
from toconline_mcp.tools.products import (
    ProductAttributes,
    ProductUpdateAttributes,
    create_product,
    delete_product,
    list_products,
    update_product,
)

# ---------------------------------------------------------------------------
# list_products
# ---------------------------------------------------------------------------


class TestListProducts:
    """Tests for the list_products read tool."""

    async def test_returns_transformed_items(self, mock_ctx, mock_api_client):
        """Happy path: JSON:API response is flattened into {id, **attributes} items."""
        mock_api_client.get.return_value = {
            "data": [
                {
                    "id": "1",
                    "attributes": {
                        "item_description": "Widget",
                        "sales_price": 9.99,
                    },
                }
            ],
            "meta": {"total": 1},
        }
        result = await list_products(mock_ctx)
        assert result["data"] == [
            {"id": "1", "item_description": "Widget", "sales_price": 9.99}
        ]

    async def test_returns_empty_data(self, mock_ctx, mock_api_client):
        """Empty data list is returned as an empty set."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        result = await list_products(mock_ctx)
        assert result == {"data": [], "meta": {}}

    async def test_calls_correct_endpoint(self, mock_ctx, mock_api_client):
        """GET /api/products is the endpoint called."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_products(mock_ctx)
        args, _ = mock_api_client.get.call_args
        assert args[0] == "/api/products"

    async def test_passes_pagination_params(self, mock_ctx, mock_api_client):
        """page and per_page are forwarded as page[number] and page[size]."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_products(mock_ctx, page=2, per_page=10)
        _, kwargs = mock_api_client.get.call_args
        assert kwargs["params"]["page[number]"] == "2"
        assert kwargs["params"]["page[size]"] == "10"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client
    ):
        """TOCOnlineError is caught and re-raised as ToolError."""
        mock_api_client.get.side_effect = TOCOnlineError(
            [{"code": "500", "detail": "Server error"}], 500
        )
        with pytest.raises(ToolError):
            await list_products(mock_ctx)


# ---------------------------------------------------------------------------
# create_product
# ---------------------------------------------------------------------------


class TestCreateProduct:
    """Tests for the create_product write tool."""

    async def test_returns_created_product(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """Happy path: newly created product is returned with its assigned id."""
        mock_api_client.post.return_value = {
            "data": {
                "id": "77",
                "attributes": {"item_description": "Gadget", "sales_price": 49.9},
            }
        }
        attrs = ProductAttributes(
            item_description="Gadget", tax_code="NOR", sales_price=49.9
        )
        result = await create_product(mock_ctx, attributes=attrs)
        assert result["id"] == "77"
        assert result["item_description"] == "Gadget"

    async def test_posts_to_correct_endpoint(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """POST /api/products is the endpoint called."""
        mock_api_client.post.return_value = {"data": {"id": "1", "attributes": {}}}
        attrs = ProductAttributes(item_description="P", tax_code="NOR", sales_price=1.0)
        await create_product(mock_ctx, attributes=attrs)
        args, _ = mock_api_client.post.call_args
        assert args[0] == "/api/products"

    async def test_payload_type_is_products(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """The JSON:API type in the nested payload object is 'products'."""
        mock_api_client.post.return_value = {"data": {"id": "1", "attributes": {}}}
        attrs = ProductAttributes(item_description="P", tax_code="NOR", sales_price=1.0)
        await create_product(mock_ctx, attributes=attrs)
        _, kwargs = mock_api_client.post.call_args
        assert kwargs["json"]["data"]["type"] == "products"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """TOCOnlineError from a failed POST is re-raised as ToolError."""
        mock_api_client.post.side_effect = TOCOnlineError(
            [{"code": "400", "detail": "Invalid tax code"}], 400
        )
        attrs = ProductAttributes(
            item_description="Bad", tax_code="???", sales_price=1.0
        )
        with pytest.raises(ToolError):
            await create_product(mock_ctx, attributes=attrs)


# ---------------------------------------------------------------------------
# update_product
# ---------------------------------------------------------------------------


class TestUpdateProduct:
    """Tests for the update_product write tool."""

    async def test_returns_updated_product(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """Happy path: updated product attributes are returned."""
        mock_api_client.patch.return_value = {
            "data": {"id": "77", "attributes": {"sales_price": 59.9}}
        }
        attrs = ProductUpdateAttributes(sales_price=59.9)
        result = await update_product(mock_ctx, product_id="77", attributes=attrs)
        assert result["id"] == "77"
        assert result["sales_price"] == 59.9

    async def test_patches_to_correct_endpoint(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """PATCH /api/products is the endpoint called."""
        mock_api_client.patch.return_value = {"data": {"id": "1", "attributes": {}}}
        await update_product(
            mock_ctx,
            product_id="1",
            attributes=ProductUpdateAttributes(is_active=False),
        )
        args, _ = mock_api_client.patch.call_args
        assert args[0] == "/api/products"

    async def test_payload_embeds_product_id(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """The product ID is embedded in the JSON:API payload."""
        mock_api_client.patch.return_value = {"data": {"id": "8", "attributes": {}}}
        await update_product(
            mock_ctx,
            product_id="8",
            attributes=ProductUpdateAttributes(notes="updated"),
        )
        _, kwargs = mock_api_client.patch.call_args
        assert kwargs["json"]["data"]["id"] == "8"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """TOCOnlineError from a failed PATCH is re-raised as ToolError."""
        mock_api_client.patch.side_effect = TOCOnlineError(
            [{"code": "404", "detail": "Not found"}], 404
        )
        with pytest.raises(ToolError):
            await update_product(
                mock_ctx,
                product_id="999",
                attributes=ProductUpdateAttributes(notes="x"),
            )

    async def test_update_product_invalid_id_raises_tool_error(
        self, mock_ctx, patch_settings
    ) -> None:
        """A non-numeric product_id raises ToolError before any API call."""
        with pytest.raises(ToolError):
            await update_product(
                mock_ctx,
                product_id="abc!",
                attributes=ProductUpdateAttributes(notes="x"),
            )
        mock_ctx.request_context.lifespan_context["api_client"].patch.assert_not_called()


# ---------------------------------------------------------------------------
# delete_product
# ---------------------------------------------------------------------------


class TestDeleteProduct:
    """Tests for the delete_product write tool."""

    async def test_returns_meta_on_success(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """Happy path: the meta confirmation dict is returned."""
        mock_api_client.delete.return_value = {"meta": {"result": "deleted"}}
        result = await delete_product(mock_ctx, product_id="77")
        assert result == {"result": "deleted"}

    async def test_calls_correct_endpoint(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """DELETE /api/products/{id} is the endpoint called."""
        mock_api_client.delete.return_value = {"meta": {"result": "deleted"}}
        await delete_product(mock_ctx, product_id="77")
        args, _ = mock_api_client.delete.call_args
        assert args[0] == "/api/products/77"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """TOCOnlineError from a failed DELETE is re-raised as ToolError."""
        mock_api_client.delete.side_effect = TOCOnlineError(
            [{"code": "403", "detail": "Referenced by documents"}], 403
        )
        with pytest.raises(ToolError):
            await delete_product(mock_ctx, product_id="1")

    async def test_delete_product_invalid_id_raises_tool_error(
        self, mock_ctx, patch_settings
    ) -> None:
        """A non-numeric product_id raises ToolError before any API call."""
        with pytest.raises(ToolError):
            await delete_product(mock_ctx, product_id="abc!")
        mock_ctx.request_context.lifespan_context["api_client"].delete.assert_not_called()
