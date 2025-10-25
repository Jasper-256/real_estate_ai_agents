"""
Bright Data MCP generic client
"""
import os
from contextlib import AsyncExitStack
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


class BrightDataClient:
    """Generic client that can call any Bright Data MCP tool dynamically."""

    def __init__(self):
        self.session = None
        self._stack = AsyncExitStack()
        self._connected = False
        self.token = os.getenv("BRIGHT_DATA_API_KEY")

    async def connect(self):
        if self._connected:
            return
        url = f"https://mcp.brightdata.com/mcp?token={self.token}"
        read_stream, write_stream, _ = await self._stack.enter_async_context(
            streamablehttp_client(url)
        )
        self.session = await self._stack.enter_async_context(
            ClientSession(read_stream, write_stream)
        )
        await self.session.initialize()
        self._connected = True

    async def disconnect(self):
        if self._connected:
            await self._stack.aclose()
            self._connected = False
            self.session = None

    async def call(self, tool: str, arguments: dict):
        """Call any MCP tool by name with arguments"""
        await self.connect()
        result = await self.session.call_tool(tool, arguments)
        if not result or not result.content:
            return {"success": False, "error": "No content returned"}
        return {
            "success": True,
            "output": result.content[0].text
        }
