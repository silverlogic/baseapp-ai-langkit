"""
Base integration tests for MCP server.

This module provides base test classes that can be extended by projects
to test their specific MCP server implementations.
"""

import json
import re
import socket
import time
import typing
from abc import ABC, abstractmethod
from multiprocessing import Process
from uuid import uuid4

import httpx
import pytest
from django.test import TransactionTestCase
from django.utils import timezone
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from freezegun import freeze_time

pytestmark = pytest.mark.django_db

# Helper to parse either a JSON body or an SSE `data:` event payload
_SSE_DATA_RE = re.compile(r"(?m)^data:\s*(.*)$")


def extract_json_from_resp(resp):
    """Return parsed JSON from an httpx.Response.

    Handles pure JSON responses and SSE bodies that contain one or more
    `data:` lines containing JSON.
    """
    try:
        return resp.json()
    except Exception:
        pass

    text = resp.text or ""
    # collect all `data:` lines
    matches = _SSE_DATA_RE.findall(text)
    if matches:
        payload = "\n".join(m.strip() for m in matches if m.strip())
        try:
            return json.loads(payload)
        except Exception:
            # try the first match as a fallback
            return json.loads(matches[0])

    # fallback: try to find first JSON-like substring
    idx = None
    for ch in ("{", "["):
        pos = text.find(ch)
        if pos != -1 and (idx is None or pos < idx):
            idx = pos
    if idx is not None:
        return json.loads(text[idx:])

    raise ValueError("No JSON payload found in response")


class MCPServerBaseTestCase(TransactionTestCase, ABC):
    """
    A TestCase that spins up a local MCP server on a separate process.

    Subclasses must implement get_mcp_server() to provide the MCP server instance.
    """

    __test__ = False  # Don't collect this abstract base class as a test

    @property
    def mcp_server_host(self) -> str:
        # Use an explicit IPv4 loopback address to avoid IPv6/localhost
        # resolution issues in test environments.
        return "127.0.0.1"

    @property
    def mcp_server_port(self) -> int:
        return 51000 + (hash(self.__class__.__name__) % 1000)

    @property
    def mcp_server_url(self) -> str:
        return f"http://{self.mcp_server_host}:{self.mcp_server_port}/mcp"

    @abstractmethod
    def get_mcp_server(self):
        """
        Return the MCP server instance to test.

        This should be implemented by subclasses to return their specific
        MCP server instance (e.g., from apps.mcp.app import mcp).
        """
        pass

    @abstractmethod
    def create_test_user(self, email: str):
        """
        Create a test user with the given email.

        This should be implemented by subclasses to create a user using
        their project's user factory/model.
        """
        pass

    @abstractmethod
    def create_test_api_key(self, user, expiry_date=None):
        """
        Create a test API key for the given user.

        This should be implemented by subclasses to create an API key using
        their project's API key factory/model.

        Returns:
            tuple: (api_key_instance, unencrypted_api_key_string)
        """
        pass

    @abstractmethod
    def get_valid_email_domain(self) -> str:
        """
        Return a valid email domain for testing (e.g., 'tsl.io').

        This is used to create valid test users that pass email validation.
        """
        pass

    @abstractmethod
    def get_invalid_email_domain(self) -> str:
        """
        Return an invalid email domain for testing (e.g., 'google.com').

        This is used to test authentication failures with invalid users.
        """
        pass

    def setUp(self):
        self.mcp = self.get_mcp_server()
        self.proc = Process(
            target=self.mcp.run_streamable_http,
            kwargs={
                "host": self.mcp_server_host,
                "port": self.mcp_server_port,
            },
            daemon=True,
        )
        self.proc.start()

        # Wait for server to be running
        max_attempts = 10
        attempt = 0
        while attempt < max_attempts and self.proc.is_alive():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect((self.mcp_server_host, self.mcp_server_port))
                    break
            except ConnectionRefusedError:
                if attempt < 3:
                    time.sleep(0.01)
                else:
                    time.sleep(0.1)
                attempt += 1
        else:
            raise RuntimeError(f"Server failed to start after {max_attempts} attempts")

    def tearDown(self):
        self.proc.terminate()
        self.proc.join(timeout=5)
        if self.proc.is_alive():
            # If it's still alive, then force kill it
            self.proc.kill()
            self.proc.join(timeout=2)
        assert self.proc.is_alive() is False


class MCPTool_Base_TestCase(MCPServerBaseTestCase):
    """
    A TestCase that sets up the client so subclasses can test the call_tool function.
    """

    __test__ = False  # Don't collect this abstract base class as a test

    async def on_client_connected(self, client: Client) -> typing.NoReturn:
        """
        Perform call_tool tests here.

        Override this method in subclasses to test specific tool calls.
        """
        pass

    @pytest.mark.asyncio
    async def test_fails_without_api_key(self):
        transport = StreamableHttpTransport(
            url=self.mcp_server_url, headers={"Accept": "text/event-stream, application/json"}
        )

        try:
            async with Client(transport=transport) as client:
                await self.on_client_connected(client=client)
        except httpx.HTTPStatusError as e:
            assert e.response.status_code == 401

    @pytest.mark.asyncio
    async def test_fails_with_invalid_api_key(self):
        transport = StreamableHttpTransport(
            url=self.mcp_server_url,
            headers={"Accept": "text/event-stream, application/json", "HTTP-API-KEY": "1234"},
        )

        try:
            async with Client(transport=transport) as client:
                await self.on_client_connected(client=client)
        except httpx.HTTPStatusError as e:
            assert e.response.status_code == 401

    @pytest.mark.asyncio
    async def test_fails_with_expired_api_key(self):
        from asgiref.sync import sync_to_async

        user = await sync_to_async(self.create_test_user)(
            email=f"{uuid4()}@{self.get_valid_email_domain()}"
        )
        api_key_instance, unencrypted_api_key = await sync_to_async(self.create_test_api_key)(
            user=user, expiry_date=timezone.now() + timezone.timedelta(days=1)
        )

        transport = StreamableHttpTransport(
            url=self.mcp_server_url,
            headers={
                "HTTP-API-KEY": unencrypted_api_key,
                "Accept": "text/event-stream, application/json",
            },
        )

        with freeze_time((timezone.now() + timezone.timedelta(days=1)).strftime("%Y-%m-%d")):
            try:
                async with Client(transport=transport) as client:
                    await self.on_client_connected(client=client)
            except RuntimeError as e:
                assert e.args[0] == "Client failed to connect: All connection attempts failed"

    @pytest.mark.asyncio
    async def test_fails_with_valid_api_key_and_invalid_user(self):
        from asgiref.sync import sync_to_async

        user = await sync_to_async(self.create_test_user)(
            email=f"{uuid4()}@{self.get_invalid_email_domain()}"
        )
        api_key_instance, unencrypted_api_key = await sync_to_async(self.create_test_api_key)(
            user=user, expiry_date=timezone.now() + timezone.timedelta(days=1)
        )

        transport = StreamableHttpTransport(
            url=self.mcp_server_url,
            headers={
                "HTTP-API-KEY": unencrypted_api_key,
                "Accept": "text/event-stream, application/json",
            },
        )

        with freeze_time((timezone.now() + timezone.timedelta(days=1)).strftime("%Y-%m-%d")):
            try:
                async with Client(transport=transport) as client:
                    await self.on_client_connected(client=client)
            except httpx.HTTPStatusError as e:
                assert e.response.status_code == 401

    @pytest.mark.asyncio
    async def test_works_with_valid_api_key_and_valid_user(self):
        from asgiref.sync import sync_to_async

        user = await sync_to_async(self.create_test_user)(
            email=f"{uuid4()}@{self.get_valid_email_domain()}"
        )
        api_key_instance, unencrypted_api_key = await sync_to_async(self.create_test_api_key)(
            user=user
        )

        transport = StreamableHttpTransport(
            url=self.mcp_server_url,
            headers={
                "HTTP-API-KEY": unencrypted_api_key,
                "Accept": "text/event-stream, application/json",
            },
        )

        async with Client(transport=transport) as client:
            await self.on_client_connected(client=client)


class TestToolsListBase(MCPServerBaseTestCase):
    """
    Base integration test: request tools list via HTTP.

    Subclasses should override get_expected_tools() to specify which tools
    should be present in the tools list.
    """

    __test__ = False  # Don't collect this abstract base class as a test

    def get_expected_tools(self) -> list[str]:
        """
        Return a list of tool names that should be present in the tools list.

        Override this method in subclasses to specify project-specific tools.
        """
        return []

    def test_tools_list_contains_expected_tools(self):
        # Create a valid user and API key
        user = self.create_test_user(email=f"{uuid4()}@{self.get_valid_email_domain()}")
        api_key_instance, unencrypted_api_key = self.create_test_api_key(user=user)

        headers = {
            "HTTP-API-KEY": unencrypted_api_key,
            # Streamable-HTTP endpoint expects the same Accept header used by the client
            "Accept": "text/event-stream, application/json",
            "Content-Type": "application/json",
        }

        # Use a valid JSON-RPC request so the Streamable-HTTP server can parse it
        payload = {
            "jsonrpc": "2.0",
            "id": str(uuid4()),
            "method": "tools/list",
            "params": {},
        }

        resp = httpx.post(self.mcp_server_url, json=payload, headers=headers, timeout=10.0)
        assert resp.status_code == 200
        data = extract_json_from_resp(resp)

        tools = None
        if isinstance(data, dict):
            source = data.get("result") if isinstance(data.get("result"), dict) else data
            tools = source.get("tools")

        assert tools is not None, f"Unexpected tools list response: {data}"

        # Normalize to dict by name
        tools_by_name = {t.get("name"): t for t in tools}

        # Check that all expected tools are present
        expected_tools = self.get_expected_tools()
        for tool_name in expected_tools:
            assert tool_name in tools_by_name, f"{tool_name} tool not listed"

        # Check read-only flag if present
        for tool_name in expected_tools:
            info = tools_by_name.get(tool_name)
            if info and "annotations" in info and "readOnlyHint" in info["annotations"]:
                assert info["annotations"]["readOnlyHint"] is True
