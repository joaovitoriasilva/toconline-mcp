"""Tests for toconline_mcp.tools.contacts.

Covers list_contacts, get_contact, create_contact, update_contact, and
delete_contact for happy paths, error propagation, and API path verification.
"""

from __future__ import annotations

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from toconline_mcp.client import TOCOnlineError
from toconline_mcp.tools.contacts import (
    ContactAttributes,
    ContactUpdateAttributes,
    create_contact,
    delete_contact,
    get_contact,
    list_contacts,
    update_contact,
)

# ---------------------------------------------------------------------------
# list_contacts
# ---------------------------------------------------------------------------


class TestListContacts:
    """Tests for the list_contacts read tool."""

    async def test_returns_list_of_contacts(self, mock_ctx, mock_api_client):
        """Happy path: JSON:API response is flattened into a list of
        {id, **attributes}."""
        mock_api_client.get.return_value = {
            "data": [
                {"id": "1", "attributes": {"email": "a@test.pt", "name": "Ana"}},
                {"id": "2", "attributes": {"email": "b@test.pt", "name": "Bruno"}},
            ]
        }
        result = await list_contacts(mock_ctx)
        assert len(result) == 2
        assert result[0] == {"id": "1", "email": "a@test.pt", "name": "Ana"}

    async def test_returns_empty_list_when_no_contacts(self, mock_ctx, mock_api_client):
        """Empty data list returns an empty Python list."""
        mock_api_client.get.return_value = {"data": []}
        result = await list_contacts(mock_ctx)
        assert result == []

    async def test_calls_correct_endpoint(self, mock_ctx, mock_api_client):
        """GET /api/contacts is the endpoint called."""
        mock_api_client.get.return_value = {"data": []}
        await list_contacts(mock_ctx)
        args, _ = mock_api_client.get.call_args
        assert args[0] == "/api/contacts"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client
    ):
        """TOCOnlineError is caught and re-raised as ToolError."""
        mock_api_client.get.side_effect = TOCOnlineError(
            [{"code": "500", "detail": "Server error"}], 500
        )
        with pytest.raises(ToolError):
            await list_contacts(mock_ctx)


# ---------------------------------------------------------------------------
# get_contact
# ---------------------------------------------------------------------------


class TestGetContact:
    """Tests for the get_contact read tool."""

    async def test_returns_flattened_contact(self, mock_ctx, mock_api_client):
        """Happy path: data dict is flattened into {id, **attributes}."""
        mock_api_client.get.return_value = {
            "data": {"id": "7", "attributes": {"email": "c@test.pt", "name": "Carlos"}}
        }
        result = await get_contact(mock_ctx, contact_id="7")
        assert result == {"id": "7", "email": "c@test.pt", "name": "Carlos"}

    async def test_calls_correct_endpoint(self, mock_ctx, mock_api_client):
        """GET /api/contacts/{id} is the endpoint called."""
        mock_api_client.get.return_value = {"data": {"id": "7", "attributes": {}}}
        await get_contact(mock_ctx, contact_id="7")
        args, _ = mock_api_client.get.call_args
        assert args[0] == "/api/contacts/7"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client
    ):
        """TOCOnlineError is caught and re-raised as ToolError."""
        mock_api_client.get.side_effect = TOCOnlineError(
            [{"code": "404", "detail": "Not found"}], 404
        )
        with pytest.raises(ToolError):
            await get_contact(mock_ctx, contact_id="0")

    async def test_get_contact_invalid_id_raises_tool_error(self, mock_ctx) -> None:
        """A non-numeric contact_id raises ToolError before any API call."""
        with pytest.raises(ToolError):
            await get_contact(mock_ctx, contact_id="abc!")
        mock_ctx.request_context.lifespan_context["api_client"].get.assert_not_called()


# ---------------------------------------------------------------------------
# create_contact
# ---------------------------------------------------------------------------


class TestCreateContact:
    """Tests for the create_contact write tool."""

    async def test_returns_created_contact(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """Happy path: newly created contact dict is returned with its assigned id."""
        mock_api_client.post.return_value = {
            "data": {"id": "50", "attributes": {"email": "new@test.pt"}}
        }
        attrs = ContactAttributes(
            email="new@test.pt",
            contactable_id=42,
            contactable_type="Customer",
        )
        result = await create_contact(mock_ctx, attributes=attrs)
        assert result == {"id": "50", "email": "new@test.pt"}

    async def test_posts_to_correct_endpoint(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """POST /api/contacts is the endpoint called."""
        mock_api_client.post.return_value = {"data": {"id": "1", "attributes": {}}}
        attrs = ContactAttributes(
            email="x@y.pt",
            contactable_id=1,
            contactable_type="Supplier",
        )
        await create_contact(mock_ctx, attributes=attrs)
        args, _ = mock_api_client.post.call_args
        assert args[0] == "/api/contacts"

    async def test_payload_type_is_contacts(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """The JSON:API type in the payload is 'contacts'."""
        mock_api_client.post.return_value = {"data": {"id": "1", "attributes": {}}}
        attrs = ContactAttributes(
            email="y@z.pt",
            contactable_id=1,
            contactable_type="Customer",
        )
        await create_contact(mock_ctx, attributes=attrs)
        _, kwargs = mock_api_client.post.call_args
        assert kwargs["json"]["data"]["type"] == "contacts"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """TOCOnlineError from a failed POST is re-raised as ToolError."""
        mock_api_client.post.side_effect = TOCOnlineError(
            [{"code": "422", "detail": "Invalid email"}], 422
        )
        attrs = ContactAttributes(
            email="bad",
            contactable_id=1,
            contactable_type="Customer",
        )
        with pytest.raises(ToolError):
            await create_contact(mock_ctx, attributes=attrs)


# ---------------------------------------------------------------------------
# update_contact
# ---------------------------------------------------------------------------


class TestUpdateContact:
    """Tests for the update_contact write tool."""

    async def test_returns_updated_contact(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """Happy path: updated contact attributes are returned."""
        mock_api_client.patch.return_value = {
            "data": {"id": "7", "attributes": {"email": "updated@test.pt"}}
        }
        attrs = ContactUpdateAttributes(email="updated@test.pt")
        result = await update_contact(mock_ctx, contact_id="7", attributes=attrs)
        assert result["id"] == "7"
        assert result["email"] == "updated@test.pt"

    async def test_patches_to_correct_endpoint(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """PATCH /api/contacts is the endpoint called (id embedded in payload)."""
        mock_api_client.patch.return_value = {"data": {"id": "1", "attributes": {}}}
        await update_contact(
            mock_ctx,
            contact_id="1",
            attributes=ContactUpdateAttributes(name="New Name"),
        )
        args, _ = mock_api_client.patch.call_args
        assert args[0] == "/api/contacts"

    async def test_payload_embeds_contact_id(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """The contact ID is embedded in the JSON:API payload."""
        mock_api_client.patch.return_value = {"data": {"id": "9", "attributes": {}}}
        await update_contact(
            mock_ctx,
            contact_id="9",
            attributes=ContactUpdateAttributes(name="X"),
        )
        _, kwargs = mock_api_client.patch.call_args
        assert kwargs["json"]["data"]["id"] == "9"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """TOCOnlineError from a failed PATCH is re-raised as ToolError."""
        mock_api_client.patch.side_effect = TOCOnlineError(
            [{"code": "404", "detail": "Not found"}], 404
        )
        with pytest.raises(ToolError):
            await update_contact(
                mock_ctx,
                contact_id="999",
                attributes=ContactUpdateAttributes(name="X"),
            )

    async def test_update_contact_invalid_id_raises_tool_error(
        self, mock_ctx, patch_settings
    ) -> None:
        """A non-numeric contact_id raises ToolError before any API call."""
        with pytest.raises(ToolError):
            await update_contact(
                mock_ctx,
                contact_id="abc!",
                attributes=ContactUpdateAttributes(name="X"),
            )
        mock_ctx.request_context.lifespan_context[
            "api_client"
        ].patch.assert_not_called()


# ---------------------------------------------------------------------------
# delete_contact
# ---------------------------------------------------------------------------


class TestDeleteContact:
    """Tests for the delete_contact write tool."""

    async def test_returns_meta_on_success(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """Happy path: the meta confirmation dict is returned."""
        mock_api_client.delete.return_value = {"meta": {"result": "deleted"}}
        result = await delete_contact(mock_ctx, contact_id="7")
        assert result == {"result": "deleted"}

    async def test_calls_correct_endpoint(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """DELETE /api/contacts/{id} is the endpoint called."""
        mock_api_client.delete.return_value = {"meta": {"result": "deleted"}}
        await delete_contact(mock_ctx, contact_id="7")
        args, _ = mock_api_client.delete.call_args
        assert args[0] == "/api/contacts/7"

    async def test_propagates_toc_online_error_as_tool_error(
        self, mock_ctx, mock_api_client, patch_settings
    ):
        """TOCOnlineError from a failed DELETE is re-raised as ToolError."""
        mock_api_client.delete.side_effect = TOCOnlineError(
            [{"code": "404", "detail": "Not found"}], 404
        )
        with pytest.raises(ToolError):
            await delete_contact(mock_ctx, contact_id="888")

    async def test_delete_contact_invalid_id_raises_tool_error(
        self, mock_ctx, patch_settings
    ) -> None:
        """A non-numeric contact_id raises ToolError before any API call."""
        with pytest.raises(ToolError):
            await delete_contact(mock_ctx, contact_id="abc!")
        mock_ctx.request_context.lifespan_context[
            "api_client"
        ].delete.assert_not_called()
