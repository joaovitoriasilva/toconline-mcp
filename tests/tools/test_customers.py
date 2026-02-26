"""Tests for toconline_mcp.tools.customers.

Covers list_customers, get_customer, create_customer, update_customer,
and delete_customer for happy paths, error propagation, and parameter
forwarding.
"""

from __future__ import annotations

import pytest

from mcp.server.fastmcp.exceptions import ToolError
from toconline_mcp.client import TOCOnlineError
from toconline_mcp.tools.customers import (
    CustomerAttributes,
    CustomerUpdateAttributes,
    create_customer,
    delete_customer,
    get_customer,
    list_customers,
    update_customer,
)

# ---------------------------------------------------------------------------
# list_customers
# ---------------------------------------------------------------------------


class TestListCustomers:
    """Tests for the list_customers read tool."""

    async def test_returns_transformed_items(self, mock_ctx, mock_api_client):
        """Happy path: JSON:API response is flattened into {id, **attributes} items."""
        mock_api_client.get.return_value = {
            "data": [{"id": "1", "attributes": {"business_name": "Acme Lda"}}],
            "meta": {"total": 1},
        }
        result = await list_customers(mock_ctx)
        assert result["data"] == [{"id": "1", "business_name": "Acme Lda"}]
        assert result["meta"] == {"total": 1}

    async def test_returns_empty_data_when_no_customers(
        self, mock_ctx, mock_api_client
    ):
        """Empty data list is returned intact as an empty list."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        result = await list_customers(mock_ctx)
        assert result == {"data": [], "meta": {}}

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client
    ):
        """TOCOnlineError from the API client is caught and re-raised as ToolError."""
        mock_api_client.get.side_effect = TOCOnlineError(
            [{"code": "500", "detail": "Server error"}], 500
        )
        with pytest.raises(ToolError):
            await list_customers(mock_ctx)

    async def test_passes_business_name_filter(self, mock_ctx, mock_api_client):
        """business_name is forwarded as filter[business_name] query parameter."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_customers(mock_ctx, business_name="Acme")
        _, kwargs = mock_api_client.get.call_args
        assert kwargs["params"]["filter[business_name]"] == "Acme"

    async def test_passes_tax_registration_number_filter(
        self, mock_ctx, mock_api_client
    ):
        """tax_registration_number is forwarded as filter[tax_registration_number]."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_customers(mock_ctx, tax_registration_number="123456789")
        _, kwargs = mock_api_client.get.call_args
        assert kwargs["params"]["filter[tax_registration_number]"] == "123456789"

    async def test_passes_pagination_params(self, mock_ctx, mock_api_client):
        """page and per_page are forwarded as page[number] and page[size]."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_customers(mock_ctx, page=2, per_page=10)
        _, kwargs = mock_api_client.get.call_args
        assert kwargs["params"]["page[number]"] == "2"
        assert kwargs["params"]["page[size]"] == "10"

    async def test_calls_correct_endpoint(self, mock_ctx, mock_api_client):
        """GET /api/customers is the endpoint called."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_customers(mock_ctx)
        args, _ = mock_api_client.get.call_args
        assert args[0] == "/api/customers"

    async def test_list_customers_no_filters_sends_no_filter_params(
        self, mock_ctx: MagicMock, mock_api_client: MagicMock
    ) -> None:
        """With no filter args, no filter keys appear in the params dict."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_customers(mock_ctx)
        _, kwargs = mock_api_client.get.call_args
        params = kwargs.get("params", {})
        assert not any(k.startswith("filter[") for k in params)


# ---------------------------------------------------------------------------
# get_customer
# ---------------------------------------------------------------------------


class TestGetCustomer:
    """Tests for the get_customer read tool."""

    async def test_returns_flattened_customer(self, mock_ctx, mock_api_client):
        """Happy path: the data dict is flattened into {id, **attributes}."""
        mock_api_client.get.return_value = {
            "data": {
                "id": "42",
                "attributes": {"business_name": "Acme Lda", "email": "a@acme.pt"},
            }
        }
        result = await get_customer(mock_ctx, customer_id="42")
        assert result == {"id": "42", "business_name": "Acme Lda", "email": "a@acme.pt"}

    async def test_calls_correct_endpoint(self, mock_ctx, mock_api_client):
        """GET /api/customers/{id} is the endpoint called."""
        mock_api_client.get.return_value = {"data": {"id": "7", "attributes": {}}}
        await get_customer(mock_ctx, customer_id="7")
        args, _ = mock_api_client.get.call_args
        assert args[0] == "/api/customers/7"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client
    ):
        """TOCOnlineError is caught and re-raised as ToolError."""
        mock_api_client.get.side_effect = TOCOnlineError(
            [{"code": "404", "detail": "Not found"}], 404
        )
        with pytest.raises(ToolError):
            await get_customer(mock_ctx, customer_id="999")

    async def test_get_customer_invalid_id_raises_tool_error(
        self, mock_ctx: MagicMock
    ) -> None:
        """A non-numeric customer_id raises ToolError before any API call."""
        with pytest.raises(ToolError):
            await get_customer(mock_ctx, customer_id="abc!")
        mock_ctx.request_context.lifespan_context["api_client"].get.assert_not_called()


# ---------------------------------------------------------------------------
# create_customer
# ---------------------------------------------------------------------------


class TestCreateCustomer:
    """Tests for the create_customer write tool."""

    async def test_returns_created_customer(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """Happy path: newly created customer is returned with its assigned id."""
        mock_api_client.post.return_value = {
            "data": {"id": "99", "attributes": {"business_name": "New Co Lda"}}
        }
        attrs = CustomerAttributes(
            business_name="New Co Lda", tax_registration_number="123456789"
        )
        result = await create_customer(mock_ctx, attributes=attrs)
        assert result == {"id": "99", "business_name": "New Co Lda"}

    async def test_posts_to_correct_endpoint(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """POST /api/customers is the endpoint called."""
        mock_api_client.post.return_value = {"data": {"id": "1", "attributes": {}}}
        attrs = CustomerAttributes(
            business_name="Co", tax_registration_number="999999990"
        )
        await create_customer(mock_ctx, attributes=attrs)
        args, _ = mock_api_client.post.call_args
        assert args[0] == "/api/customers"

    async def test_payload_contains_customer_type(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """The JSON:API payload type is set to 'customers'."""
        mock_api_client.post.return_value = {"data": {"id": "1", "attributes": {}}}
        attrs = CustomerAttributes(
            business_name="Co", tax_registration_number="999999990"
        )
        await create_customer(mock_ctx, attributes=attrs)
        _, kwargs = mock_api_client.post.call_args
        assert kwargs["json"]["data"]["type"] == "customers"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """TOCOnlineError from a failed POST is re-raised as ToolError."""
        mock_api_client.post.side_effect = TOCOnlineError(
            [{"code": "400", "detail": "Invalid NIF"}], 400
        )
        attrs = CustomerAttributes(
            business_name="Co", tax_registration_number="000000000"
        )
        with pytest.raises(ToolError):
            await create_customer(mock_ctx, attributes=attrs)


# ---------------------------------------------------------------------------
# update_customer
# ---------------------------------------------------------------------------


class TestUpdateCustomer:
    """Tests for the update_customer write tool."""

    async def test_returns_updated_customer(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """Happy path: the patched customer attributes are returned."""
        mock_api_client.patch.return_value = {
            "data": {"id": "42", "attributes": {"email": "new@acme.pt"}}
        }
        attrs = CustomerUpdateAttributes(email="new@acme.pt")
        result = await update_customer(mock_ctx, customer_id="42", attributes=attrs)
        assert result["id"] == "42"
        assert result["email"] == "new@acme.pt"

    async def test_patches_to_correct_endpoint(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """PATCH /api/customers is the endpoint called."""
        mock_api_client.patch.return_value = {"data": {"id": "1", "attributes": {}}}
        await update_customer(
            mock_ctx,
            customer_id="1",
            attributes=CustomerUpdateAttributes(business_name="Updated"),
        )
        args, _ = mock_api_client.patch.call_args
        assert args[0] == "/api/customers"

    async def test_payload_embeds_customer_id(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """The customer ID is embedded in the JSON:API payload."""
        mock_api_client.patch.return_value = {"data": {"id": "5", "attributes": {}}}
        await update_customer(
            mock_ctx,
            customer_id="5",
            attributes=CustomerUpdateAttributes(email="x@y.com"),
        )
        _, kwargs = mock_api_client.patch.call_args
        assert kwargs["json"]["data"]["id"] == "5"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """TOCOnlineError from a failed PATCH is re-raised as ToolError."""
        mock_api_client.patch.side_effect = TOCOnlineError(
            [{"code": "422", "detail": "Unprocessable"}], 422
        )
        with pytest.raises(ToolError):
            await update_customer(
                mock_ctx,
                customer_id="1",
                attributes=CustomerUpdateAttributes(email="bad"),
            )

    async def test_update_customer_invalid_id_raises_tool_error(
        self, mock_ctx: MagicMock, patch_settings: MagicMock
    ) -> None:
        """A non-numeric customer_id raises ToolError before any API call."""
        with pytest.raises(ToolError):
            await update_customer(
                mock_ctx,
                customer_id="abc!",
                attributes=CustomerUpdateAttributes(email="x@y.com"),
            )
        mock_ctx.request_context.lifespan_context["api_client"].patch.assert_not_called()


# ---------------------------------------------------------------------------
# delete_customer
# ---------------------------------------------------------------------------


class TestDeleteCustomer:
    """Tests for the delete_customer write tool."""

    async def test_returns_meta_on_success(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """Happy path: the meta confirmation object is returned."""
        mock_api_client.delete.return_value = {"meta": {"result": "deleted"}}
        result = await delete_customer(mock_ctx, customer_id="42")
        assert result == {"result": "deleted"}

    async def test_calls_correct_endpoint(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """DELETE /api/customers/{id} is the endpoint called."""
        mock_api_client.delete.return_value = {"meta": {"result": "deleted"}}
        await delete_customer(mock_ctx, customer_id="42")
        args, _ = mock_api_client.delete.call_args
        assert args[0] == "/api/customers/42"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """TOCOnlineError from a failed DELETE is re-raised as ToolError."""
        mock_api_client.delete.side_effect = TOCOnlineError(
            [{"code": "403", "detail": "Has documents"}], 403
        )
        with pytest.raises(ToolError):
            await delete_customer(mock_ctx, customer_id="99")

    async def test_delete_customer_invalid_id_raises_tool_error(
        self, mock_ctx: MagicMock, patch_settings: MagicMock
    ) -> None:
        """A non-numeric customer_id raises ToolError before any API call."""
        with pytest.raises(ToolError):
            await delete_customer(mock_ctx, customer_id="abc!")
        mock_ctx.request_context.lifespan_context["api_client"].delete.assert_not_called()
