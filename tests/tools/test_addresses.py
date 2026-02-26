"""Tests for toconline_mcp.tools.addresses.

Covers get_address, create_address, update_address, and delete_address
for happy paths, error propagation, and API path verification.
"""

from __future__ import annotations

import pytest

from mcp.server.fastmcp.exceptions import ToolError
from toconline_mcp.client import TOCOnlineError
from toconline_mcp.tools.addresses import (
    AddressAttributes,
    AddressUpdateAttributes,
    create_address,
    delete_address,
    get_address,
    update_address,
)

# ---------------------------------------------------------------------------
# get_address
# ---------------------------------------------------------------------------


class TestGetAddress:
    """Tests for the get_address read tool."""

    async def test_returns_flattened_address(self, mock_ctx, mock_api_client):
        """Happy path: data dict is flattened into {id, **attributes}."""
        mock_api_client.get.return_value = {
            "data": {
                "id": "20",
                "attributes": {"address_detail": "Rua do Ouro, 1", "city": "Lisboa"},
            }
        }
        result = await get_address(mock_ctx, address_id="20")
        assert result == {
            "id": "20",
            "address_detail": "Rua do Ouro, 1",
            "city": "Lisboa",
        }

    async def test_calls_correct_endpoint(self, mock_ctx, mock_api_client):
        """GET /api/addresses/{id} is the endpoint called."""
        mock_api_client.get.return_value = {"data": {"id": "20", "attributes": {}}}
        await get_address(mock_ctx, address_id="20")
        args, _ = mock_api_client.get.call_args
        assert args[0] == "/api/addresses/20"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client
    ):
        """TOCOnlineError is caught and re-raised as ToolError."""
        mock_api_client.get.side_effect = TOCOnlineError(
            [{"code": "404", "detail": "Not found"}], 404
        )
        with pytest.raises(ToolError):
            await get_address(mock_ctx, address_id="999")

    async def test_get_address_invalid_id_raises_tool_error(
        self, mock_ctx
    ) -> None:
        """A non-numeric address_id raises ToolError before any API call."""
        with pytest.raises(ToolError):
            await get_address(mock_ctx, address_id="abc!")
        mock_ctx.request_context.lifespan_context["api_client"].get.assert_not_called()


# ---------------------------------------------------------------------------
# create_address
# ---------------------------------------------------------------------------


class TestCreateAddress:
    """Tests for the create_address write tool."""

    async def test_returns_created_address(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """Happy path: newly created address is returned with its assigned id."""
        mock_api_client.post.return_value = {
            "data": {
                "id": "30",
                "attributes": {"address_detail": "Av. da Liberdade, 10"},
            }
        }
        attrs = AddressAttributes(
            address_detail="Av. da Liberdade, 10",
            addressable_id=42,
            addressable_type="Customer",
        )
        result = await create_address(mock_ctx, attributes=attrs)
        assert result == {"id": "30", "address_detail": "Av. da Liberdade, 10"}

    async def test_posts_to_correct_endpoint(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """POST /api/addresses is the endpoint called."""
        mock_api_client.post.return_value = {"data": {"id": "1", "attributes": {}}}
        attrs = AddressAttributes(
            address_detail="Rua A, 1",
            addressable_id=1,
            addressable_type="Customer",
        )
        await create_address(mock_ctx, attributes=attrs)
        args, _ = mock_api_client.post.call_args
        assert args[0] == "/api/addresses"

    async def test_payload_type_is_addresses(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """The JSON:API type in the payload is 'addresses'."""
        mock_api_client.post.return_value = {"data": {"id": "1", "attributes": {}}}
        attrs = AddressAttributes(
            address_detail="Rua B, 2",
            addressable_id=1,
            addressable_type="Supplier",
        )
        await create_address(mock_ctx, attributes=attrs)
        _, kwargs = mock_api_client.post.call_args
        assert kwargs["json"]["data"]["type"] == "addresses"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """TOCOnlineError from a failed POST is re-raised as ToolError."""
        mock_api_client.post.side_effect = TOCOnlineError(
            [{"code": "422", "detail": "Invalid addressable"}], 422
        )
        attrs = AddressAttributes(
            address_detail="X",
            addressable_id=0,
            addressable_type="Customer",
        )
        with pytest.raises(ToolError):
            await create_address(mock_ctx, attributes=attrs)


# ---------------------------------------------------------------------------
# update_address
# ---------------------------------------------------------------------------


class TestUpdateAddress:
    """Tests for the update_address write tool."""

    async def test_returns_updated_address(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """Happy path: updated address attributes are returned."""
        mock_api_client.patch.return_value = {
            "data": {"id": "20", "attributes": {"city": "Porto"}}
        }
        attrs = AddressUpdateAttributes(city="Porto")
        result = await update_address(mock_ctx, address_id="20", attributes=attrs)
        assert result["id"] == "20"
        assert result["city"] == "Porto"

    async def test_patches_to_correct_endpoint(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """PATCH /api/addresses is the endpoint called (id is in the payload)."""
        mock_api_client.patch.return_value = {"data": {"id": "1", "attributes": {}}}
        await update_address(
            mock_ctx,
            address_id="1",
            attributes=AddressUpdateAttributes(city="Lisboa"),
        )
        args, _ = mock_api_client.patch.call_args
        assert args[0] == "/api/addresses"

    async def test_payload_embeds_address_id(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """The address ID is embedded in the JSON:API payload."""
        mock_api_client.patch.return_value = {"data": {"id": "5", "attributes": {}}}
        await update_address(
            mock_ctx,
            address_id="5",
            attributes=AddressUpdateAttributes(postcode="1000-001"),
        )
        _, kwargs = mock_api_client.patch.call_args
        assert kwargs["json"]["data"]["id"] == "5"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """TOCOnlineError from a failed PATCH is re-raised as ToolError."""
        mock_api_client.patch.side_effect = TOCOnlineError(
            [{"code": "404", "detail": "Not found"}], 404
        )
        with pytest.raises(ToolError):
            await update_address(
                mock_ctx,
                address_id="999",
                attributes=AddressUpdateAttributes(city="X"),
            )

    async def test_update_address_invalid_id_raises_tool_error(
        self, mock_ctx, patch_settings
    ) -> None:
        """A non-numeric address_id raises ToolError before any API call."""
        with pytest.raises(ToolError):
            await update_address(
                mock_ctx,
                address_id="abc!",
                attributes=AddressUpdateAttributes(city="Lisboa"),
            )
        mock_ctx.request_context.lifespan_context["api_client"].patch.assert_not_called()


# ---------------------------------------------------------------------------
# delete_address
# ---------------------------------------------------------------------------


class TestDeleteAddress:
    """Tests for the delete_address write tool."""

    async def test_returns_meta_on_success(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """Happy path: the meta confirmation dict is returned."""
        mock_api_client.delete.return_value = {"meta": {"result": "deleted"}}
        result = await delete_address(mock_ctx, address_id="20")
        assert result == {"result": "deleted"}

    async def test_calls_correct_endpoint(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """DELETE /api/addresses/{id} is the endpoint called."""
        mock_api_client.delete.return_value = {"meta": {"result": "deleted"}}
        await delete_address(mock_ctx, address_id="20")
        args, _ = mock_api_client.delete.call_args
        assert args[0] == "/api/addresses/20"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """TOCOnlineError from a failed DELETE is re-raised as ToolError."""
        mock_api_client.delete.side_effect = TOCOnlineError(
            [{"code": "404", "detail": "Not found"}], 404
        )
        with pytest.raises(ToolError):
            await delete_address(mock_ctx, address_id="999")

    async def test_delete_address_invalid_id_raises_tool_error(
        self, mock_ctx, patch_settings
    ) -> None:
        """A non-numeric address_id raises ToolError before any API call."""
        with pytest.raises(ToolError):
            await delete_address(mock_ctx, address_id="abc!")
        mock_ctx.request_context.lifespan_context["api_client"].delete.assert_not_called()
