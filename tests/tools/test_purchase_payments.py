"""Tests for toconline_mcp.tools.purchase_payments.

Covers list_purchase_payments, get_purchase_payment, create_purchase_payment,
update_purchase_payment, and delete_purchase_payment for happy paths, error
propagation, and API path verification.
"""

from __future__ import annotations

import pytest

from mcp.server.fastmcp.exceptions import ToolError
from toconline_mcp.client import TOCOnlineError
from toconline_mcp.tools.purchase_payments import (
    PurchasePaymentAttributes,
    PurchasePaymentUpdateAttributes,
    create_purchase_payment,
    delete_purchase_payment,
    get_purchase_payment,
    list_purchase_payments,
    update_purchase_payment,
)

# ---------------------------------------------------------------------------
# list_purchase_payments
# ---------------------------------------------------------------------------


class TestListPurchasePayments:
    """Tests for the list_purchase_payments read tool."""

    async def test_returns_transformed_items(self, mock_ctx, mock_api_client):
        """Happy path: JSON:API response is flattened into {id, **attributes} items."""
        mock_api_client.get.return_value = {
            "data": [
                {
                    "id": "400",
                    "attributes": {"date": "2025-03-01", "gross_total": 1200.0},
                }
            ],
            "meta": {"total": 1},
        }
        result = await list_purchase_payments(mock_ctx)
        assert result["data"][0] == {
            "id": "400",
            "date": "2025-03-01",
            "gross_total": 1200.0,
        }

    async def test_calls_correct_endpoint(self, mock_ctx, mock_api_client):
        """GET /api/v1/commercial_purchases_payments is the endpoint called."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_purchase_payments(mock_ctx)
        args, _ = mock_api_client.get.call_args
        assert args[0] == "/api/v1/commercial_purchases_payments"

    async def test_passes_pagination_params(self, mock_ctx, mock_api_client):
        """page and per_page are forwarded as page[number] and page[size]."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_purchase_payments(mock_ctx, page=3, per_page=10)
        _, kwargs = mock_api_client.get.call_args
        assert kwargs["params"]["page[number]"] == "3"
        assert kwargs["params"]["page[size]"] == "10"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client
    ):
        """TOCOnlineError is caught and re-raised as ToolError."""
        mock_api_client.get.side_effect = TOCOnlineError(
            [{"code": "500", "detail": "Server error"}], 500
        )
        with pytest.raises(ToolError):
            await list_purchase_payments(mock_ctx)


# ---------------------------------------------------------------------------
# get_purchase_payment
# ---------------------------------------------------------------------------


class TestGetPurchasePayment:
    """Tests for the get_purchase_payment read tool."""

    async def test_returns_flattened_payment(self, mock_ctx, mock_api_client):
        """Happy path: data dict is flattened into {id, **attributes}."""
        mock_api_client.get.return_value = {
            "data": {
                "id": "400",
                "attributes": {"date": "2025-03-01", "payment_mechanism": "TB"},
            }
        }
        result = await get_purchase_payment(mock_ctx, payment_id="400")
        assert result == {
            "id": "400",
            "date": "2025-03-01",
            "payment_mechanism": "TB",
        }

    async def test_calls_correct_endpoint(self, mock_ctx, mock_api_client):
        """GET /api/v1/commercial_purchases_payments/{id} is the endpoint called."""
        mock_api_client.get.return_value = {"data": {"id": "400", "attributes": {}}}
        await get_purchase_payment(mock_ctx, payment_id="400")
        args, _ = mock_api_client.get.call_args
        assert args[0] == "/api/v1/commercial_purchases_payments/400"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client
    ):
        """TOCOnlineError is caught and re-raised as ToolError."""
        mock_api_client.get.side_effect = TOCOnlineError(
            [{"code": "404", "detail": "Not found"}], 404
        )
        with pytest.raises(ToolError):
            await get_purchase_payment(mock_ctx, payment_id="999")

    async def test_get_purchase_payment_invalid_id_raises_tool_error(
        self, mock_ctx
    ) -> None:
        """A non-numeric payment_id raises ToolError before any API call."""
        with pytest.raises(ToolError):
            await get_purchase_payment(mock_ctx, payment_id="abc!")
        mock_ctx.request_context.lifespan_context["api_client"].get.assert_not_called()


# ---------------------------------------------------------------------------
# create_purchase_payment
# ---------------------------------------------------------------------------


class TestCreatePurchasePayment:
    """Tests for the create_purchase_payment write tool."""

    def _minimal_attrs(self) -> PurchasePaymentAttributes:
        """Return minimal valid PurchasePaymentAttributes for testing."""
        return PurchasePaymentAttributes(
            date="2025-03-01",
            document_series_id=1,
            gross_total=1200.0,
            net_total=975.6,
            payment_mechanism="TB",
            supplier_id=55,
        )

    async def test_returns_created_payment(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """Happy path: newly created payment is returned with its assigned id."""
        mock_api_client.post.return_value = {
            "data": {
                "id": "500",
                "attributes": {"date": "2025-03-01", "gross_total": 1200.0},
            }
        }
        result = await create_purchase_payment(
            mock_ctx, attributes=self._minimal_attrs()
        )
        assert result["id"] == "500"

    async def test_posts_to_v1_endpoint(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """POST /api/v1/commercial_purchases_payments is the endpoint called."""
        mock_api_client.post.return_value = {"data": {"id": "1", "attributes": {}}}
        await create_purchase_payment(mock_ctx, attributes=self._minimal_attrs())
        args, _ = mock_api_client.post.call_args
        assert args[0] == "/api/v1/commercial_purchases_payments"

    async def test_sends_flat_payload(self, mock_ctx, mock_api_client, patch_settings):
        """The POST payload is a flat JSON body (no JSON:API wrapper)."""
        mock_api_client.post.return_value = {"data": {"id": "1", "attributes": {}}}
        await create_purchase_payment(mock_ctx, attributes=self._minimal_attrs())
        _, kwargs = mock_api_client.post.call_args
        assert "date" in kwargs["json"]
        assert kwargs["json"]["payment_mechanism"] == "TB"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """TOCOnlineError from a failed POST is re-raised as ToolError."""
        mock_api_client.post.side_effect = TOCOnlineError(
            [{"code": "422", "detail": "Invalid series"}], 422
        )
        with pytest.raises(ToolError):
            await create_purchase_payment(mock_ctx, attributes=self._minimal_attrs())


# ---------------------------------------------------------------------------
# update_purchase_payment
# ---------------------------------------------------------------------------


class TestUpdatePurchasePayment:
    """Tests for the update_purchase_payment write tool."""

    async def test_returns_updated_payment(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """Happy path: updated payment attributes are returned."""
        mock_api_client.patch.return_value = {
            "data": {"id": "400", "attributes": {"observations": "Updated note"}}
        }
        attrs = PurchasePaymentUpdateAttributes(observations="Updated note")
        result = await update_purchase_payment(
            mock_ctx, payment_id="400", attributes=attrs
        )
        assert result["id"] == "400"
        assert result["observations"] == "Updated note"

    async def test_patches_to_legacy_endpoint(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """PATCH /api/commercial_purchases_payments/{id} (legacy path) is called."""
        mock_api_client.patch.return_value = {"data": {"id": "400", "attributes": {}}}
        await update_purchase_payment(
            mock_ctx,
            payment_id="400",
            attributes=PurchasePaymentUpdateAttributes(observations="x"),
        )
        args, _ = mock_api_client.patch.call_args
        assert args[0] == "/api/commercial_purchases_payments/400"

    async def test_payload_embeds_payment_id(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """The payment ID is embedded in the JSON:API payload."""
        mock_api_client.patch.return_value = {"data": {"id": "400", "attributes": {}}}
        await update_purchase_payment(
            mock_ctx,
            payment_id="400",
            attributes=PurchasePaymentUpdateAttributes(observations="y"),
        )
        _, kwargs = mock_api_client.patch.call_args
        assert kwargs["json"]["data"]["id"] == "400"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """TOCOnlineError from a failed PATCH is re-raised as ToolError."""
        mock_api_client.patch.side_effect = TOCOnlineError(
            [{"code": "404", "detail": "Not found"}], 404
        )
        with pytest.raises(ToolError):
            await update_purchase_payment(
                mock_ctx,
                payment_id="999",
                attributes=PurchasePaymentUpdateAttributes(observations="z"),
            )


# ---------------------------------------------------------------------------
# delete_purchase_payment
# ---------------------------------------------------------------------------


class TestDeletePurchasePayment:
    """Tests for the delete_purchase_payment write tool."""

    async def test_returns_meta_on_success(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """Happy path: the meta confirmation dict is returned."""
        mock_api_client.delete.return_value = {"meta": {"result": "deleted"}}
        result = await delete_purchase_payment(mock_ctx, payment_id="400")
        assert result == {"result": "deleted"}

    async def test_calls_legacy_endpoint(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """DELETE /api/commercial_purchases_payments/{id} (legacy path) is called."""
        mock_api_client.delete.return_value = {"meta": {"result": "deleted"}}
        await delete_purchase_payment(mock_ctx, payment_id="400")
        args, _ = mock_api_client.delete.call_args
        assert args[0] == "/api/commercial_purchases_payments/400"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """TOCOnlineError from a failed DELETE is re-raised as ToolError."""
        mock_api_client.delete.side_effect = TOCOnlineError(
            [{"code": "403", "detail": "Cannot delete finalized"}], 403
        )
        with pytest.raises(ToolError):
            await delete_purchase_payment(mock_ctx, payment_id="400")

    async def test_delete_purchase_payment_invalid_id_raises_tool_error(
        self, mock_ctx, patch_settings
    ) -> None:
        """A non-numeric payment_id raises ToolError before any API call."""
        with pytest.raises(ToolError):
            await delete_purchase_payment(mock_ctx, payment_id="abc!")
        mock_ctx.request_context.lifespan_context[
            "api_client"
        ].delete.assert_not_called()
