"""MCP Client implementation for connecting to external MCP servers."""

import json
import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class MCPClient:
    """Client for connecting to external MCP servers.

    Allows NaLaMap to discover and use tools from external MCP servers,
    enabling integration with third-party AI tools and services.
    """

    def __init__(self, server_url: str, timeout: float = 30.0):
        """Initialize MCP client.

        Args:
            server_url: Base URL of the MCP server
            timeout: Request timeout in seconds (default: 30)
        """
        self.server_url = server_url.rstrip("/")
        self.session = httpx.AsyncClient(timeout=timeout)
        self.initialized = False
        self.server_info: Optional[Dict[str, Any]] = None
        self.available_tools: list = []
        self._request_id = 0

    def _get_next_id(self) -> int:
        """Get next request ID."""
        self._request_id += 1
        return self._request_id

    async def initialize(self):
        """Initialize connection to MCP server.

        Exchanges capabilities and retrieves server information.
        Must be called before using other methods.

        Raises:
            httpx.HTTPError: If connection fails
            Exception: If server returns error
        """
        response = await self._send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "nalamap-client",
                    "version": "1.0.0",
                },
            },
        )

        self.server_info = response.get("result", {})
        self.initialized = True

        logger.info(f"Connected to MCP server: {self.server_url}")

        # List available tools
        await self.list_tools()

    async def list_tools(self) -> list:
        """Get list of available tools from server.

        Returns:
            List of tool definitions

        Raises:
            Exception: If not initialized or request fails
        """
        if not self.initialized:
            await self.initialize()

        response = await self._send_request("tools/list", {})
        self.available_tools = response.get("result", {}).get("tools", [])

        logger.info(f"Loaded {len(self.available_tools)} tools from {self.server_url}")

        return self.available_tools

    async def call_tool(self, tool_name: str, arguments: Dict) -> Any:
        """Call a tool on the MCP server.

        Args:
            tool_name: Name of the tool to call
            arguments: Tool arguments as dictionary

        Returns:
            Tool result (parsed from JSON if possible)

        Raises:
            Exception: If tool execution fails or returns error
        """
        if not self.initialized:
            await self.initialize()

        response = await self._send_request(
            "tools/call",
            {
                "name": tool_name,
                "arguments": arguments,
            },
        )

        result = response.get("result", {})

        # Check for errors
        if result.get("isError"):
            content = result.get("content", [{}])[0]
            error_text = content.get("text", "Unknown error")
            raise Exception(f"Tool error: {error_text}")

        # Extract text content
        content = result.get("content", [{}])[0]
        text = content.get("text", "{}")

        # Try to parse as JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Return as string if not JSON
            return text

    async def _send_request(self, method: str, params: Dict) -> Dict:
        """Send MCP JSON-RPC request to server.

        Args:
            method: MCP method name
            params: Method parameters

        Returns:
            Response from server

        Raises:
            httpx.HTTPError: If HTTP request fails
            Exception: If server returns error response
        """
        request = {
            "jsonrpc": "2.0",
            "id": self._get_next_id(),
            "method": method,
            "params": params,
        }

        try:
            response = await self.session.post(
                f"{self.server_url}/",
                json=request,
            )
            response.raise_for_status()

            data = response.json()

            # Check for JSON-RPC error
            if "error" in data:
                error = data["error"]
                raise Exception(f"MCP error {error.get('code')}: {error.get('message')}")

            return data

        except httpx.HTTPError as e:
            logger.error(f"HTTP error connecting to MCP server: {e}")
            raise

    async def close(self):
        """Close client connection.

        Should be called when done using the client to release resources.
        """
        await self.session.aclose()
        logger.info(f"Closed connection to MCP server: {self.server_url}")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
