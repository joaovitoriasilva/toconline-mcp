"""Tests for toconline_mcp.tools.services.

Covers list_services, create_service, update_service, and delete_service
for happy paths, error propagation, and API path verification.
"""

from __future__ import annotations

import pytest

from mcp.server.fastmcp.exceptions import ToolError
from toconline_mcp.client import TOCOnlineError
from toconline_mcp.tools.services import (
    ServiceAttributes,
    ServiceUpdateAttributes,
    create_service,
    delete_service,
    list_services,
    update_service,
)

# ---------------------------------------------------------------------------
# list_services
# ---------------------------------------------------------------------------


class TestListServices:
    """Tests for the list_services read tool."""

    async def test_returns_transformed_items(self, mock_ctx, mock_api_client):
        """Happy path: JSON:API response is flattened into {id, **attributes} items."""
        mock_api_client.get.return_value = {
            "data": [
                {
                    "id": "10",
                    "attributes": {
                        "item_description": "Consultoria",
                        "sales_price": 100.0,
                    },
                }
            ],
            "meta": {"total": 1},
        }
        result = await list_services(mock_ctx)
        assert result["data"] == [
            {"id": "10", "item_description": "Consultoria", "sales_price": 100.0}
        ]

    async def test_returns_empty_data(self, mock_ctx, mock_api_client):
        """Empty data list is returned as an empty set."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        result = await list_services(mock_ctx)
        assert result == {"data": [], "meta": {}}

    async def test_calls_correct_endpoint(self, mock_ctx, mock_api_client):
        """GET /api/services is the endpoint called."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_services(mock_ctx)
        args, _ = mock_api_client.get.call_args
        assert args[0] == "/api/services"

    async def test_passes_pagination_params(self, mock_ctx, mock_api_client):
        """page and per_page are forwarded as page[number] and page[size]."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_services(mock_ctx, page=1, per_page=25)
        _, kwargs = mock_api_client.get.call_args
        assert kwargs["params"]["page[number]"] == "1"
        assert kwargs["params"]["page[size]"] == "25"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client
    ):
        """TOCOnlineError is caught and re-raised as ToolError."""
        mock_api_client.get.side_effect = TOCOnlineError(
            [{"code": "503", "detail": "Unavailable"}], 503
        )
        with pytest.raises(ToolError):
            await list_services(mock_ctx)


# ---------------------------------------------------------------------------
# create_service
# ---------------------------------------------------------------------------


class TestCreateService:
    """Tests for the create_service write tool."""

    async def test_returns_created_service(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """Happy path: newly created service is returned with its assigned id."""
        mock_api_client.post.return_value = {
            "data": [
                {
                    "id": "20",
                    "attributes": {
                        "item_description": "Formação",
                        "sales_price": 200.0,
                    },
                }
            ]
        }
        attrs = ServiceAttributes(item_description="Formação", sales_price=200.0)
        result = await create_service(mock_ctx, attributes=attrs)
        assert result["id"] == "20"
        assert result["item_description"] == "Formação"

    async def test_posts_to_correct_endpoint(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """POST /api/services is the endpoint called."""
        mock_api_client.post.return_value = {"data": [{"id": "1", "attributes": {}}]}
        attrs = ServiceAttributes(item_description="S", sales_price=1.0)
        await create_service(mock_ctx, attributes=attrs)
        args, _ = mock_api_client.post.call_args
        assert args[0] == "/api/services"

    async def test_payload_is_list_with_service_type(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """The POST payload is a list whose first item has type 'services'."""
        mock_api_client.post.return_value = {"data": [{"id": "1", "attributes": {}}]}
        attrs = ServiceAttributes(item_description="S", sales_price=1.0)
        await create_service(mock_ctx, attributes=attrs)
        _, kwargs = mock_api_client.post.call_args
        payload_list = kwargs["json"]["data"]
        assert isinstance(payload_list, list)
        assert payload_list[0]["type"] == "services"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """TOCOnlineError from a failed POST is re-raised as ToolError."""
        mock_api_client.post.side_effect = TOCOnlineError(
            [{"code": "400", "detail": "Bad request"}], 400
        )
        attrs = ServiceAttributes(item_description="Bad", sales_price=0.0)
        with pytest.raises(ToolError):
            await create_service(mock_ctx, attributes=attrs)


# ---------------------------------------------------------------------------
# update_service
# ---------------------------------------------------------------------------


class TestUpdateService:
    """Tests for the update_service write tool."""

    async def test_returns_updated_service(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """Happy path: updated service attributes are returned."""
        mock_api_client.patch.return_value = {
            "data": {"id": "20", "attributes": {"sales_price": 250.0}}
        }
        attrs = ServiceUpdateAttributes(sales_price=250.0)
        result = await update_service(mock_ctx, service_id="20", attributes=attrs)
        assert result["id"] == "20"
        assert result["sales_price"] == 250.0

    async def test_patches_to_correct_endpoint(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """PATCH /api/services is the endpoint called."""
        mock_api_client.patch.return_value = {"data": {"id": "1", "attributes": {}}}
        await update_service(
            mock_ctx,
            service_id="1",
            attributes=ServiceUpdateAttributes(is_active=False),
        )
        args, _ = mock_api_client.patch.call_args
        assert args[0] == "/api/services"

    async def test_payload_embeds_service_id(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """The service ID is embedded in the JSON:API payload."""
        mock_api_client.patch.return_value = {"data": {"id": "15", "attributes": {}}}
        await update_service(
            mock_ctx,
            service_id="15",
            attributes=ServiceUpdateAttributes(notes="revised"),
        )
        _, kwargs = mock_api_client.patch.call_args
        assert kwargs["json"]["data"]["id"] == "15"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """TOCOnlineError from a failed PATCH is re-raised as ToolError."""
        mock_api_client.patch.side_effect = TOCOnlineError(
            [{"code": "404", "detail": "Not found"}], 404
        )
        with pytest.raises(ToolError):
            await update_service(
                mock_ctx,
                service_id="999",
                attributes=ServiceUpdateAttributes(notes="x"),
            )

    async def test_update_service_invalid_id_raises_tool_error(
        self, mock_ctx, patch_settings
    ) -> None:
        """A non-numeric service_id raises ToolError before any API call."""
        with pytest.raises(ToolError):
            await update_service(
                mock_ctx,
                service_id="abc!",
                attributes=ServiceUpdateAttributes(notes="x"),
            )
        mock_ctx.request_context.lifespan_context["api_client"].patch.assert_not_called()


# ---------------------------------------------------------------------------
# delete_service
# ---------------------------------------------------------------------------


class TestDeleteService:
    """Tests for the delete_service write tool."""

    async def test_returns_meta_on_success(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """Happy path: the meta confirmation dict is returned."""
        mock_api_client.delete.return_value = {"meta": {"result": "deleted"}}
        result = await delete_service(mock_ctx, service_id="20")
        assert result == {"result": "deleted"}

    async def test_calls_correct_endpoint(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """DELETE /api/services (with id in body) is the endpoint called."""
        mock_api_client.delete.return_value = {"meta": {"result": "deleted"}}
        await delete_service(mock_ctx, service_id="20")
        args, _ = mock_api_client.delete.call_args
        assert args[0] == "/api/services"

    async def test_payload_embeds_service_id(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """The service ID is embedded in the JSON body of the DELETE request."""
        mock_api_client.delete.return_value = {"meta": {"result": "deleted"}}
        await delete_service(mock_ctx, service_id="20")
        _, kwargs = mock_api_client.delete.call_args
        assert kwargs["json"]["data"]["id"] == "20"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """TOCOnlineError from a failed DELETE is re-raised as ToolError."""
        mock_api_client.delete.side_effect = TOCOnlineError(
            [{"code": "403", "detail": "Referenced"}], 403
        )
        with pytest.raises(ToolError):
            await delete_service(mock_ctx, service_id="99")

    async def test_delete_service_invalid_id_raises_tool_error(
        self, mock_ctx, patch_settings
    ) -> None:
        """A non-numeric service_id raises ToolError before any API call."""
        with pytest.raises(ToolError):
            await delete_service(mock_ctx, service_id="abc!")
        mock_ctx.request_context.lifespan_context["api_client"].delete.assert_not_called()
