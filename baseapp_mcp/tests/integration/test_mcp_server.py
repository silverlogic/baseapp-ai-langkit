"""
Base integration tests for MCP server.

This module provides base test classes that can be extended by projects
to test their specific MCP server implementations.
"""

import typing
from abc import ABC, abstractmethod
from contextlib import contextmanager
from urllib.parse import urljoin
from uuid import uuid4

import httpx
import pytest
from baseapp_api_key.tests.factories import APIKeyFactory
from channels.db import database_sync_to_async
from django.contrib.auth.models import Permission
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.utilities.tests import run_server_in_process
from freezegun import freeze_time

from baseapp_ai_langkit.tests.factories import UserFactory
from baseapp_mcp.extensions.fastmcp.client.auth.api_key import APIKeyAuth
from baseapp_mcp.permissions.models import MCPToolPermission
from baseapp_mcp.server.django_fastmcp import DjangoFastMCP

pytestmark = pytest.mark.django_db


class MCPServerBaseTestCase(TransactionTestCase, ABC):
    """
    A TestCase that spins up a local MCP server on a separate process.

    Subclasses must implement get_mcp_server() to provide the MCP server instance.
    """

    @abstractmethod
    def get_mcp_server(self):
        """
        Return the MCP server instance to test.

        This should be implemented by subclasses to return their specific
        MCP server instance (e.g., from apps.mcp.app import mcp).
        """
        pass

    @contextmanager
    def run_mcp_server(self) -> typing.Iterator[str]:
        mcp = self.get_mcp_server()
        with run_server_in_process(
            mcp.run,
            transport="streamable-http",
            show_banner=False,
        ) as url:
            yield urljoin(url, "mcp")


class MCPServerTestCase_ApiKey(MCPServerBaseTestCase):
    def get_mcp_server(self) -> DjangoFastMCP:
        mcp = DjangoFastMCP.create(name="LangkitTest MCP")
        return mcp

    async def on_client_connected(self, client: Client) -> typing.NoReturn:
        pass

    @pytest.mark.asyncio
    async def test_fails_without_api_key(self):
        with self.run_mcp_server() as mcp_url:
            transport = StreamableHttpTransport(
                url=mcp_url,
                headers={
                    "Accept": "text/event-stream, application/json",
                },
            )

            try:
                async with Client(transport=transport) as client:
                    await self.on_client_connected(client=client)
            except httpx.HTTPStatusError as e:
                assert e.response.status_code == 401

    @pytest.mark.asyncio
    async def test_fails_with_invalid_api_key(self):
        with self.run_mcp_server() as mcp_url:
            transport = StreamableHttpTransport(
                url=mcp_url,
                headers={"Accept": "text/event-stream, application/json", "HTTP-API-KEY": "1234"},
            )

            try:
                async with Client(transport=transport) as client:
                    await self.on_client_connected(client=client)
            except httpx.HTTPStatusError as e:
                assert e.response.status_code == 401

    @pytest.mark.asyncio
    async def test_fails_with_expired_api_key(self):
        user = await database_sync_to_async(UserFactory)(email=f"{uuid4()}@tsl.io")
        api_key = await database_sync_to_async(APIKeyFactory)(
            user=user, expiry_date=timezone.now() + timezone.timedelta(days=1)
        )

        with self.run_mcp_server() as mcp_url:
            transport = StreamableHttpTransport(
                url=mcp_url,
                headers={
                    "Accept": "text/event-stream, application/json",
                },
                auth=APIKeyAuth(api_key=api_key),
            )

            with freeze_time((timezone.now() + timezone.timedelta(days=1)).strftime("%Y-%m-%d")):
                try:
                    async with Client(transport=transport) as client:
                        await self.on_client_connected(client=client)
                except RuntimeError as e:
                    assert e.args[0] == "Client failed to connect: All connection attempts failed"

    @pytest.mark.asyncio
    async def test_fails_with_valid_api_key_and_invalid_user(self):
        user = await database_sync_to_async(UserFactory)(email=f"{uuid4()}@gmail.com")
        api_key = await database_sync_to_async(APIKeyFactory)(
            user=user, expiry_date=timezone.now() + timezone.timedelta(days=1)
        )

        with self.run_mcp_server() as mcp_url:
            transport = StreamableHttpTransport(
                url=mcp_url,
                headers={
                    "Accept": "text/event-stream, application/json",
                },
                auth=APIKeyAuth(api_key=api_key),
            )

            with freeze_time((timezone.now() + timezone.timedelta(days=1)).strftime("%Y-%m-%d")):
                try:
                    async with Client(transport=transport) as client:
                        await self.on_client_connected(client=client)
                except httpx.HTTPStatusError as e:
                    assert e.response.status_code == 401

    @pytest.mark.asyncio
    async def test_works_with_valid_api_key_and_valid_user(self):
        user = await database_sync_to_async(UserFactory)(email=f"{uuid4()}@tsl.io")
        api_key = await database_sync_to_async(APIKeyFactory)(user=user)

        with self.run_mcp_server() as mcp_url:
            transport = StreamableHttpTransport(
                url=mcp_url,
                headers={
                    "Accept": "text/event-stream, application/json",
                },
                auth=APIKeyAuth(api_key=api_key),
            )

            async with Client(transport=transport) as client:
                await self.on_client_connected(client=client)


class MCPServerTestCase_ToolsList(MCPServerBaseTestCase):
    def get_mcp_server(self) -> DjangoFastMCP:
        mcp = DjangoFastMCP.create(name="LangkitTest MCP")
        return mcp

    async def on_client_connected(self, client: Client) -> typing.NoReturn:
        pass

    @pytest.mark.asyncio
    async def test_tools_list_for_user_with_no_permissions(self):
        from baseapp_mcp.app_settings import app_settings

        user = await database_sync_to_async(UserFactory)(email=f"{uuid4()}@tsl.io")
        api_key = await database_sync_to_async(APIKeyFactory)(user=user)

        with self.run_mcp_server() as mcp_url:
            transport = StreamableHttpTransport(
                url=mcp_url,
                headers={
                    "Accept": "text/event-stream, application/json",
                },
                auth=APIKeyAuth(api_key=api_key),
            )

            async with Client(transport=transport) as client:
                await self.on_client_connected(client=client)
                tools = await client.list_tools()
                # All users are assigned the Standard MCP Tool Access group on creation
                assert len(tools) == len(app_settings.MCP_TOOLS)

    @pytest.mark.asyncio
    @override_settings(DEBUG=True)
    async def test_tools_list_for_user_with_access_standard_mcp_tools_permission(self):
        from baseapp_mcp.app_settings import app_settings

        user = await database_sync_to_async(UserFactory)(email=f"{uuid4()}@tsl.io")
        api_key = await database_sync_to_async(APIKeyFactory)(user=user)

        with self.run_mcp_server() as mcp_url:
            transport = StreamableHttpTransport(
                url=mcp_url,
                headers={
                    "Accept": "text/event-stream, application/json",
                },
                auth=APIKeyAuth(api_key=api_key),
            )

            async with Client(transport=transport) as client:
                await self.on_client_connected(client=client)
                tools = await client.list_tools()
                # All users have access to standard mcp tools
                assert len(tools) == len(app_settings.MCP_TOOLS)

    @pytest.mark.asyncio
    @override_settings(DEBUG=True)
    async def test_tools_list_for_user_with_access_debug_mcp_tools_permission(self):
        from baseapp_mcp.app_settings import app_settings

        user = await database_sync_to_async(UserFactory)(email=f"{uuid4()}@tsl.io")
        api_key = await database_sync_to_async(APIKeyFactory)(user=user)
        permission = await Permission.objects.aget(
            content_type__app_label=MCPToolPermission._meta.app_label,
            codename="access_debug_mcp_tools",
        )

        await database_sync_to_async(user.user_permissions.add)(permission)

        with self.run_mcp_server() as mcp_url:
            transport = StreamableHttpTransport(
                url=mcp_url,
                headers={
                    "Accept": "text/event-stream, application/json",
                },
                auth=APIKeyAuth(api_key=api_key),
            )

            async with Client(transport=transport) as client:
                await self.on_client_connected(client=client)
                tools = await client.list_tools()
                # All users have access to standard mcp tools
                assert len(tools) == (
                    len(app_settings.MCP_TOOLS) + len(app_settings.DEBUG_MCP_TOOLS)
                )

    @pytest.mark.asyncio
    @override_settings(DEBUG=True)
    async def test_tools_list_for_user_with_access_experimental_tools_permission(self):
        from baseapp_mcp.app_settings import app_settings

        user = await database_sync_to_async(UserFactory)(email=f"{uuid4()}@tsl.io")
        api_key = await database_sync_to_async(APIKeyFactory)(user=user)
        permission = await Permission.objects.aget(
            content_type__app_label=MCPToolPermission._meta.app_label,
            codename="access_experimental_mcp_tools",
        )

        await database_sync_to_async(user.user_permissions.add)(permission)

        with self.run_mcp_server() as mcp_url:
            transport = StreamableHttpTransport(
                url=mcp_url,
                headers={
                    "Accept": "text/event-stream, application/json",
                },
                auth=APIKeyAuth(api_key=api_key),
            )

            async with Client(transport=transport) as client:
                await self.on_client_connected(client=client)
                tools = await client.list_tools()
                # All users have access to standard mcp tools
                assert len(tools) == (
                    len(app_settings.MCP_TOOLS) + len(app_settings.EXPERIMENTAL_MCP_TOOLS)
                )

    @pytest.mark.asyncio
    @override_settings(DEBUG=True)
    async def test_tools_list_for_user_with_all_permissions(self):
        from baseapp_mcp.app_settings import app_settings

        user = await database_sync_to_async(UserFactory)(email=f"{uuid4()}@tsl.io")
        api_key = await database_sync_to_async(APIKeyFactory)(user=user)
        permissions = await database_sync_to_async(list)(
            Permission.objects.filter(
                content_type__app_label=MCPToolPermission._meta.app_label,
                codename__in=[
                    "access_debug_mcp_tools",
                    "access_experimental_mcp_tools",
                ],
            )
        )
        await database_sync_to_async(user.user_permissions.add)(*permissions)

        with self.run_mcp_server() as mcp_url:
            transport = StreamableHttpTransport(
                url=mcp_url,
                headers={
                    "Accept": "text/event-stream, application/json",
                },
                auth=APIKeyAuth(api_key=api_key),
            )

            async with Client(transport=transport) as client:
                await self.on_client_connected(client=client)
                tools = await client.list_tools()
                # All users have access to standard mcp tools
                assert len(tools) == (
                    len(app_settings.MCP_TOOLS)
                    + len(app_settings.DEBUG_MCP_TOOLS)
                    + len(app_settings.EXPERIMENTAL_MCP_TOOLS)
                )
