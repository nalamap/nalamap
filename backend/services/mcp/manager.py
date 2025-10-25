"""MCP Manager for coordinating MCP server and client connections."""

import logging
from typing import Any, Dict, Optional

from langchain_core.tools import BaseTool

from services.mcp.integration import load_mcp_tools

logger = logging.getLogger(__name__)


class MCPManager:
    """Manages MCP server and external client connections.

    Coordinates initialization of MCP functionality:
    - Loads external MCP tools for use by NaLaMap agents
    - Manages lifecycle of MCP client connections
    - Provides centralized access to external tools
    """

    def __init__(self):
        """Initialize MCP manager."""
        self.clients: Dict[str, Any] = {}  # URL -> MCPClient
        self.external_tools: list[BaseTool] = []
        self.initialized = False

    async def initialize(self):
        """Initialize MCP connections.

        Connects to all configured external MCP servers and loads their tools.
        Safe to call multiple times - will skip if already initialized.

        Raises:
            Exception: If critical initialization fails
        """
        if self.initialized:
            logger.info("MCP manager already initialized")
            return

        from core.config import MCP_ENABLED, MCP_EXTERNAL_SERVERS

        if not MCP_ENABLED:
            logger.info("MCP support is disabled (MCP_ENABLED=false)")
            self.initialized = True
            return

        logger.info("Initializing MCP manager...")

        # Connect to external MCP servers
        for server_url in MCP_EXTERNAL_SERVERS:
            try:
                logger.info(f"Connecting to external MCP server: {server_url}")
                tools = await load_mcp_tools(server_url)
                self.external_tools.extend(tools)
                logger.info(f"✓ Loaded {len(tools)} tools from {server_url}")

            except Exception as e:
                logger.error(f"✗ Failed to connect to MCP server {server_url}: {e}")
                # Continue with other servers even if one fails

        self.initialized = True

        if self.external_tools:
            logger.info(
                f"MCP manager initialized with {len(self.external_tools)} " f"external tools"
            )
        else:
            logger.info("MCP manager initialized (no external servers configured)")

    def get_external_tools(self) -> list[BaseTool]:
        """Get all external MCP tools.

        Returns:
            List of LangChain-compatible tools from external MCP servers

        Note:
            Returns empty list if not initialized or MCP disabled.
        """
        if not self.initialized:
            logger.warning("MCPManager not initialized, returning empty tool list")
            return []

        return self.external_tools

    async def shutdown(self):
        """Shutdown MCP manager and close all connections.

        Cleans up resources and closes all active MCP client connections.
        """
        logger.info("Shutting down MCP manager...")

        # Close all client connections
        for url, client in self.clients.items():
            try:
                await client.close()
                logger.info(f"Closed connection to {url}")
            except Exception as e:
                logger.error(f"Error closing connection to {url}: {e}")

        self.clients.clear()
        self.external_tools.clear()
        self.initialized = False

        logger.info("MCP manager shutdown complete")


# Global MCP manager instance
_mcp_manager: Optional[MCPManager] = None


async def get_mcp_manager() -> MCPManager:
    """Get or create the global MCP manager instance.

    Returns:
        Initialized MCP manager

    Note:
        Creates and initializes manager on first call.
        Subsequent calls return the same instance.
    """
    global _mcp_manager

    if _mcp_manager is None:
        _mcp_manager = MCPManager()
        await _mcp_manager.initialize()

    return _mcp_manager


async def get_external_tools() -> list[BaseTool]:
    """Convenience function to get external MCP tools.

    Returns:
        List of external tools from all connected MCP servers

    Example:
        ```python
        external_tools = await get_external_tools()
        all_tools = native_tools + external_tools
        ```
    """
    manager = await get_mcp_manager()
    return manager.get_external_tools()
