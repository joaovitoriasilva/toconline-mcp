"""Tests for toconline_mcp.tools.sales_documents.

Covers list_sales_documents, get_sales_document, create_sales_document,
finalize_sales_document, delete_sales_document, get_sales_document_pdf_url,
and send_sales_document_email for happy paths, error propagation, and API
path verification.
"""

from __future__ import annotations

import pytest

from mcp.server.fastmcp.exceptions import ToolError
from toconline_mcp.client import TOCOnlineError
from toconline_mcp.tools.sales_documents import (
    SalesDocumentAttributes,
    create_sales_document,
    delete_sales_document,
    finalize_sales_document,
    get_sales_document,
    get_sales_document_pdf_url,
    list_sales_documents,
    send_sales_document_email,
)

# ---------------------------------------------------------------------------
# list_sales_documents
# ---------------------------------------------------------------------------


class TestListSalesDocuments:
    """Tests for the list_sales_documents read tool."""

    async def test_returns_transformed_items(self, mock_ctx, mock_api_client):
        """Happy path: JSON:API response is flattened into {id, **attributes} items."""
        mock_api_client.get.return_value = {
            "data": [
                {
                    "id": "100",
                    "attributes": {"document_type": "FT", "date": "2025-01-01"},
                }
            ],
            "meta": {"total": 1},
        }
        result = await list_sales_documents(mock_ctx)
        assert result["data"][0] == {
            "id": "100",
            "document_type": "FT",
            "date": "2025-01-01",
        }

    async def test_calls_correct_endpoint(self, mock_ctx, mock_api_client):
        """GET /api/v1/commercial_sales_documents/ is the endpoint called."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_sales_documents(mock_ctx)
        args, _ = mock_api_client.get.call_args
        assert args[0] == "/api/v1/commercial_sales_documents/"

    async def test_passes_status_filter(self, mock_ctx, mock_api_client):
        """status is forwarded as filter[status]."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_sales_documents(mock_ctx, status="1")
        _, kwargs = mock_api_client.get.call_args
        assert kwargs["params"]["filter[status]"] == "1"

    async def test_passes_customer_id_filter(self, mock_ctx, mock_api_client):
        """customer_id is forwarded as filter[customer_id]."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_sales_documents(mock_ctx, customer_id="42")
        _, kwargs = mock_api_client.get.call_args
        assert kwargs["params"]["filter[customer_id]"] == "42"

    async def test_passes_date_range_filters(self, mock_ctx, mock_api_client):
        """date_from and date_to are forwarded as filter[date_from] and filter[date_to]."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_sales_documents(
            mock_ctx, date_from="2025-01-01", date_to="2025-12-31"
        )
        _, kwargs = mock_api_client.get.call_args
        assert kwargs["params"]["filter[date_from]"] == "2025-01-01"
        assert kwargs["params"]["filter[date_to]"] == "2025-12-31"

    async def test_passes_pagination_params(self, mock_ctx, mock_api_client):
        """page and per_page are forwarded as page[number] and page[size]."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_sales_documents(mock_ctx, page=2, per_page=10)
        _, kwargs = mock_api_client.get.call_args
        assert kwargs["params"]["page[number]"] == "2"
        assert kwargs["params"]["page[size]"] == "10"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client
    ):
        """TOCOnlineError is caught and re-raised as ToolError."""
        mock_api_client.get.side_effect = TOCOnlineError(
            [{"code": "500", "detail": "Error"}], 500
        )
        with pytest.raises(ToolError):
            await list_sales_documents(mock_ctx)

    async def test_list_sales_documents_no_filters_sends_no_filter_params(
        self, mock_ctx, mock_api_client
    ) -> None:
        """With no filter args, no filter keys appear in the params dict."""
        mock_api_client.get.return_value = {"data": [], "meta": {}}
        await list_sales_documents(mock_ctx)
        _, kwargs = mock_api_client.get.call_args
        params = kwargs.get("params", {})
        assert not any(k.startswith("filter[") for k in params)


# ---------------------------------------------------------------------------
# get_sales_document
# ---------------------------------------------------------------------------


class TestGetSalesDocument:
    """Tests for the get_sales_document read tool."""

    async def test_returns_flattened_document(self, mock_ctx, mock_api_client):
        """Happy path: data dict is flattened into {id, **attributes}."""
        mock_api_client.get.return_value = {
            "data": {
                "id": "100",
                "attributes": {"document_type": "FT", "total": "1000.00"},
            }
        }
        result = await get_sales_document(mock_ctx, document_id="100")
        assert result == {"id": "100", "document_type": "FT", "total": "1000.00"}

    async def test_calls_correct_endpoint(self, mock_ctx, mock_api_client):
        """GET /api/v1/commercial_sales_documents/{id} is the endpoint called."""
        mock_api_client.get.return_value = {"data": {"id": "5", "attributes": {}}}
        await get_sales_document(mock_ctx, document_id="5")
        args, _ = mock_api_client.get.call_args
        assert args[0] == "/api/v1/commercial_sales_documents/5"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client
    ):
        """TOCOnlineError is caught and re-raised as ToolError."""
        mock_api_client.get.side_effect = TOCOnlineError(
            [{"code": "404", "detail": "Not found"}], 404
        )
        with pytest.raises(ToolError):
            await get_sales_document(mock_ctx, document_id="999")

    async def test_get_sales_document_invalid_id_raises_tool_error(
        self, mock_ctx
    ) -> None:
        """A non-numeric document_id raises ToolError before any API call."""
        with pytest.raises(ToolError):
            await get_sales_document(mock_ctx, document_id="abc!")
        mock_ctx.request_context.lifespan_context["api_client"].get.assert_not_called()


# ---------------------------------------------------------------------------
# create_sales_document
# ---------------------------------------------------------------------------


class TestCreateSalesDocument:
    """Tests for the create_sales_document write tool."""

    async def test_returns_created_document(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """Happy path: newly created document is returned."""
        mock_api_client.post.return_value = {
            "data": {
                "id": "200",
                "attributes": {"document_type": "FT", "date": "2025-01-15"},
            }
        }
        attrs = SalesDocumentAttributes(
            document_type="FT",
            date="2025-01-15",
            customer_tax_registration_number="999999990",
        )
        result = await create_sales_document(mock_ctx, attributes=attrs)
        assert result["id"] == "200"
        assert result["document_type"] == "FT"

    async def test_posts_to_v1_endpoint(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """POST /api/v1/commercial_sales_documents is the endpoint called."""
        mock_api_client.post.return_value = {"data": {"id": "1", "attributes": {}}}
        attrs = SalesDocumentAttributes(
            document_type="FT",
            date="2025-01-01",
            customer_tax_registration_number="999999990",
        )
        await create_sales_document(mock_ctx, attributes=attrs)
        args, _ = mock_api_client.post.call_args
        assert args[0] == "/api/v1/commercial_sales_documents"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """TOCOnlineError from a failed POST is re-raised as ToolError."""
        mock_api_client.post.side_effect = TOCOnlineError(
            [{"code": "422", "detail": "Invalid document type"}], 422
        )
        attrs = SalesDocumentAttributes(
            document_type="XX",
            date="2025-01-01",
            customer_tax_registration_number="999999990",
        )
        with pytest.raises(ToolError):
            await create_sales_document(mock_ctx, attributes=attrs)


# ---------------------------------------------------------------------------
# finalize_sales_document
# ---------------------------------------------------------------------------


class TestFinalizeSalesDocument:
    """Tests for the finalize_sales_document write tool."""

    async def test_returns_finalized_document(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """Happy path: the finalized document is returned."""
        mock_api_client.patch.return_value = {
            "data": {"id": "100", "attributes": {"status": 1}}
        }
        result = await finalize_sales_document(mock_ctx, document_id="100")
        assert result["id"] == "100"
        assert result["status"] == 1

    async def test_patches_to_correct_endpoint(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """PATCH /api/commercial_sales_documents is the endpoint called."""
        mock_api_client.patch.return_value = {"data": {"id": "1", "attributes": {}}}
        await finalize_sales_document(mock_ctx, document_id="1")
        args, _ = mock_api_client.patch.call_args
        assert args[0] == "/api/commercial_sales_documents"

    async def test_payload_sets_status_to_1(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """The payload sets status to 1 to finalize the document."""
        mock_api_client.patch.return_value = {"data": {"id": "1", "attributes": {}}}
        await finalize_sales_document(mock_ctx, document_id="1")
        _, kwargs = mock_api_client.patch.call_args
        assert kwargs["json"]["data"]["attributes"]["status"] == 1

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """TOCOnlineError from a failed PATCH is re-raised as ToolError."""
        mock_api_client.patch.side_effect = TOCOnlineError(
            [{"code": "422", "detail": "Already finalized"}], 422
        )
        with pytest.raises(ToolError):
            await finalize_sales_document(mock_ctx, document_id="100")

    async def test_finalize_sales_document_invalid_id_raises_tool_error(
        self, mock_ctx, patch_settings
    ) -> None:
        """A non-numeric document_id raises ToolError before any API call."""
        with pytest.raises(ToolError):
            await finalize_sales_document(mock_ctx, document_id="abc!")
        mock_ctx.request_context.lifespan_context["api_client"].patch.assert_not_called()


# ---------------------------------------------------------------------------
# delete_sales_document
# ---------------------------------------------------------------------------


class TestDeleteSalesDocument:
    """Tests for the delete_sales_document write tool."""

    async def test_returns_meta_on_success(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """Happy path: the meta confirmation dict is returned."""
        mock_api_client.delete.return_value = {"meta": {"result": "deleted"}}
        result = await delete_sales_document(mock_ctx, document_id="100")
        assert result == {"result": "deleted"}

    async def test_calls_correct_endpoint(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """DELETE /api/commercial_sales_documents/{id} is the endpoint called."""
        mock_api_client.delete.return_value = {"meta": {"result": "deleted"}}
        await delete_sales_document(mock_ctx, document_id="100")
        args, _ = mock_api_client.delete.call_args
        assert args[0] == "/api/commercial_sales_documents/100"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """TOCOnlineError from a failed DELETE is re-raised as ToolError."""
        mock_api_client.delete.side_effect = TOCOnlineError(
            [{"code": "403", "detail": "Cannot delete finalized"}], 403
        )
        with pytest.raises(ToolError):
            await delete_sales_document(mock_ctx, document_id="100")

    async def test_delete_sales_document_invalid_id_raises_tool_error(
        self, mock_ctx, patch_settings
    ) -> None:
        """A non-numeric document_id raises ToolError before any API call."""
        with pytest.raises(ToolError):
            await delete_sales_document(mock_ctx, document_id="abc!")
        mock_ctx.request_context.lifespan_context["api_client"].delete.assert_not_called()


# ---------------------------------------------------------------------------
# get_sales_document_pdf_url
# ---------------------------------------------------------------------------


class TestGetSalesDocumentPdfUrl:
    """Tests for the get_sales_document_pdf_url read tool."""

    async def test_builds_full_url_when_host_present(self, mock_ctx, mock_api_client):
        """When the API returns a URL object with a host, a full_url string is built."""
        mock_api_client.get.return_value = {
            "data": {
                "id": "100",
                "attributes": {
                    "url": {
                        "scheme": "https",
                        "host": "files.example.pt",
                        "path": "/docs/100.pdf",
                        "port": 443,
                    }
                },
            }
        }
        result = await get_sales_document_pdf_url(mock_ctx, document_id="100")
        assert "full_url" in result
        assert "files.example.pt" in result["full_url"]

    async def test_calls_correct_endpoint_with_filter_type(
        self, mock_ctx, mock_api_client
    ):
        """GET /api/url_for_print/{id} with filter[type]=Document is called."""
        mock_api_client.get.return_value = {"data": {"id": "100", "attributes": {}}}
        await get_sales_document_pdf_url(mock_ctx, document_id="100")
        args, kwargs = mock_api_client.get.call_args
        assert args[0] == "/api/url_for_print/100"
        assert kwargs["params"]["filter[type]"] == "Document"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client
    ):
        """TOCOnlineError is caught and re-raised as ToolError."""
        mock_api_client.get.side_effect = TOCOnlineError(
            [{"code": "404", "detail": "Not found"}], 404
        )
        with pytest.raises(ToolError):
            await get_sales_document_pdf_url(mock_ctx, document_id="999")

    async def test_get_sales_document_pdf_url_invalid_id_raises_tool_error(
        self, mock_ctx
    ) -> None:
        """A non-numeric document_id raises ToolError before any API call."""
        with pytest.raises(ToolError):
            await get_sales_document_pdf_url(mock_ctx, document_id="abc!")
        mock_ctx.request_context.lifespan_context["api_client"].get.assert_not_called()


# ---------------------------------------------------------------------------
# send_sales_document_email
# ---------------------------------------------------------------------------


class TestSendSalesDocumentEmail:
    """Tests for the send_sales_document_email write tool."""

    async def test_returns_meta_on_success(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """Happy path: the API meta/data response is returned."""
        mock_api_client.patch.return_value = {"meta": {"result": "sent"}}
        result = await send_sales_document_email(
            mock_ctx,
            document_id="100",
            to_email="cust@example.pt",
            from_email="me@company.pt",
            from_name="Company",
            subject="Your invoice",
        )
        assert result == {"result": "sent"}

    async def test_patches_to_correct_endpoint(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """PATCH /api/email/document is the endpoint called."""
        mock_api_client.patch.return_value = {"meta": {}}
        await send_sales_document_email(
            mock_ctx,
            document_id="100",
            to_email="a@b.pt",
            from_email="c@d.pt",
            from_name="X",
            subject="Y",
        )
        args, _ = mock_api_client.patch.call_args
        assert args[0] == "/api/email/document"

    async def test_payload_contains_email_fields(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """The PATCH payload includes to_email, from_email, from_name, and subject."""
        mock_api_client.patch.return_value = {"meta": {}}
        await send_sales_document_email(
            mock_ctx,
            document_id="5",
            to_email="dest@x.pt",
            from_email="orig@x.pt",
            from_name="Sender",
            subject="Invoice 5",
        )
        _, kwargs = mock_api_client.patch.call_args
        attrs = kwargs["json"]["data"]["attributes"]
        assert attrs["to_email"] == "dest@x.pt"
        assert attrs["from_email"] == "orig@x.pt"
        assert attrs["subject"] == "Invoice 5"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """TOCOnlineError from a failed PATCH is re-raised as ToolError."""
        mock_api_client.patch.side_effect = TOCOnlineError(
            [{"code": "422", "detail": "Invalid email"}], 422
        )
        with pytest.raises(ToolError):
            await send_sales_document_email(
                mock_ctx,
                document_id="1",
                to_email="bad",
                from_email="me@x.pt",
                from_name="Me",
                subject="S",
            )
