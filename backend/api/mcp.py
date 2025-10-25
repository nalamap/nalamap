"""MCP API endpoints for HTTP transport."""

import logging
from fastapi import APIRouter, HTTPException, Request

from services.mcp.server import MCPServer

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp", tags=["mcp"])

# Initialize MCP server (singleton)
mcp_server = MCPServer()


@router.post("/")
async def handle_mcp_request(request: Request):
    """Handle MCP requests over HTTP.

    Accepts MCP JSON-RPC requests and returns responses according to
    the Model Context Protocol specification.

    Example request:
    ```json
    {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    }
    ```

    Returns:
        MCP JSON-RPC response
    """
    try:
        body = await request.json()
        response = await mcp_server.handle_request(body)

        # Add JSON-RPC envelope if not present
        if "jsonrpc" not in response:
            response["jsonrpc"] = "2.0"
        if "id" not in response:
            response["id"] = body.get("id", 1)

        return response

    except Exception as e:
        logger.exception("MCP request error")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def mcp_info():
    """Get MCP server information.

    Returns metadata about the MCP server, including supported protocol
    version, available transport, and documentation links.

    Returns:
        Server information dictionary
    """
    return {
        "name": mcp_server.name,
        "protocol": "MCP",
        "version": mcp_server.PROTOCOL_VERSION,
        "transport": "http",
        "endpoint": "/api/mcp",
        "documentation": "https://modelcontextprotocol.io",
        "tools_count": len(mcp_server.tools),
        "description": "NaLaMap MCP Server - Geospatial AI tools for mapping and analysis",
    }


@router.get("/tools")
async def list_mcp_tools():
    """Get list of available MCP tools.

    Convenience endpoint to list all tools without full MCP protocol.

    Returns:
        List of tool names and descriptions
    """
    result = await mcp_server.handle_list_tools()
    return result.get("tools", [])
