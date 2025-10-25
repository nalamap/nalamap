"""MCP Server implementation for exposing NaLaMap tools."""

import asyncio
import json
import logging
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class MCPServer:
    """Model Context Protocol server for NaLaMap tools.

    Exposes NaLaMap geospatial tools through the standardized MCP protocol,
    allowing external AI assistants (Claude, ChatGPT, etc.) to use them.
    """

    # MCP protocol version
    PROTOCOL_VERSION = "2024-11-05"

    def __init__(self, name: str = "nalamap-mcp-server"):
        """Initialize MCP server.

        Args:
            name: Server name for identification
        """
        self.name = name
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.resources: Dict[str, Dict[str, Any]] = {}
        self._initialize_tools()

    def _initialize_tools(self):
        """Register all available NaLaMap tools in MCP format."""
        from services.tools.geocoding import (
            geocode_using_nominatim_to_geostate,
            geocode_using_overpass_to_geostate,
        )
        from services.tools.geoprocess_tools import geoprocess_tool
        from services.tools.styling_tools import style_map_layers
        from services.tools.attribute_tools import attribute_tool

        # Geocoding tools
        self._register_langchain_tool(
            tool=geocode_using_nominatim_to_geostate,
            name="geocode_location",
            description=(
                "Geocode a location name to geographic coordinates and create a GeoJSON layer. "
                "Use for finding places, addresses, and creating point layers on the map."
            ),
        )

        self._register_langchain_tool(
            tool=geocode_using_overpass_to_geostate,
            name="find_pois",
            description=(
                "Find Points of Interest (POIs) using OpenStreetMap Overpass API. "
                "Search for restaurants, parks, schools, hospitals, and other amenities."
            ),
        )

        # Geoprocessing tool
        self._register_langchain_tool(
            tool=geoprocess_tool,
            name="geoprocess",
            description=(
                "Perform geospatial operations on map layers: buffer, clip, union, "
                "intersect, difference, centroid, convex_hull, etc."
            ),
        )

        # Styling tool
        self._register_langchain_tool(
            tool=style_map_layers,
            name="style_layer",
            description=(
                "Apply visual styling to map layers: colors, sizes, opacity, stroke, etc. "
                "Use to customize how layers appear on the map."
            ),
        )

        # Attribute analysis tool
        self._register_langchain_tool(
            tool=attribute_tool,
            name="analyze_attributes",
            description=(
                "Analyze and query layer attributes: calculate statistics, filter features, "
                "aggregate data, and extract information from layer properties."
            ),
        )

        logger.info(f"Registered {len(self.tools)} tools for MCP server")

    def _register_langchain_tool(
        self,
        tool: Any,
        name: str,
        description: str,
    ):
        """Register a LangChain tool in MCP format.

        Args:
            tool: LangChain tool instance
            name: MCP tool name
            description: Tool description for MCP
        """
        # Extract schema from LangChain tool
        input_schema = self._extract_tool_schema(tool)

        self.tools[name] = {
            "name": name,
            "description": description,
            "inputSchema": input_schema,
            "func": tool,
        }

    def _extract_tool_schema(self, tool: Any) -> Dict[str, Any]:
        """Extract JSON schema from LangChain tool.

        Args:
            tool: LangChain tool instance

        Returns:
            JSON schema for tool inputs
        """
        # LangChain tools have args_schema attribute
        if hasattr(tool, "args_schema") and tool.args_schema:
            schema = tool.args_schema.schema()
            return {
                "type": "object",
                "properties": schema.get("properties", {}),
                "required": schema.get("required", []),
            }

        # Fallback: basic schema
        return {
            "type": "object",
            "properties": {},
            "required": [],
        }

    def _register_tool(
        self,
        name: str,
        description: str,
        tool_func: Callable,
        input_schema: Dict,
    ):
        """Register a custom tool in MCP format.

        Args:
            name: Tool name
            description: Tool description
            tool_func: Function to execute
            input_schema: JSON schema for inputs
        """
        self.tools[name] = {
            "name": name,
            "description": description,
            "inputSchema": input_schema,
            "func": tool_func,
        }

    async def handle_initialize(self, params: Dict) -> Dict[str, Any]:
        """Handle MCP initialize request.

        Returns server capabilities and metadata.

        Args:
            params: Initialize parameters from client

        Returns:
            Server capabilities and info
        """
        return {
            "protocolVersion": self.PROTOCOL_VERSION,
            "capabilities": {
                "tools": {"listChanged": True},  # We support tool list updates
                "resources": {
                    "subscribe": False,  # We don't support resource subscriptions yet
                    "listChanged": False,
                },
                "prompts": {"listChanged": False},  # We don't support prompts yet
                "logging": {},
            },
            "serverInfo": {
                "name": self.name,
                "version": "1.0.0",
                "description": "NaLaMap MCP Server - Geospatial AI tools for mapping and analysis",
            },
        }

    async def handle_list_tools(self, params: Optional[Dict] = None) -> Dict[str, Any]:
        """Handle tools/list request.

        Returns list of available tools in MCP format.

        Args:
            params: Optional parameters (not used)

        Returns:
            List of available tools
        """
        tools_list = [
            {
                "name": tool["name"],
                "description": tool["description"],
                "inputSchema": tool["inputSchema"],
            }
            for tool in self.tools.values()
        ]

        return {"tools": tools_list}

    async def handle_call_tool(self, params: Dict) -> Dict[str, Any]:
        """Handle tools/call request.

        Executes a tool and returns the result.

        Args:
            params: {
                "name": str,  # Tool name
                "arguments": dict  # Tool arguments
            }

        Returns:
            Tool execution result or error
        """
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if tool_name not in self.tools:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error: Unknown tool '{tool_name}'",
                    }
                ],
                "isError": True,
            }

        try:
            tool = self.tools[tool_name]
            tool_func = tool["func"]

            # Execute tool (handle both sync and async)
            if asyncio.iscoroutinefunction(tool_func):
                result = await tool_func.ainvoke(arguments)
            else:
                # LangChain tools use .invoke() method
                if hasattr(tool_func, "invoke"):
                    result = tool_func.invoke(arguments)
                else:
                    result = tool_func(**arguments)

            # Format result as MCP content
            # Handle different result types
            if isinstance(result, str):
                result_text = result
            elif isinstance(result, dict):
                result_text = json.dumps(result, indent=2, default=str)
            else:
                result_text = str(result)

            return {
                "content": [
                    {
                        "type": "text",
                        "text": result_text,
                    }
                ],
                "isError": False,
            }

        except Exception as e:
            logger.exception(f"Error executing tool {tool_name}")
            return {
                "content": [
                    {
                        "type": "text",
                        "text": f"Error executing tool: {str(e)}",
                    }
                ],
                "isError": True,
            }

    async def handle_request(self, request: Dict) -> Dict[str, Any]:
        """Handle incoming MCP request.

        Args:
            request: MCP request with method and params

        Returns:
            MCP response
        """
        method = request.get("method")
        params = request.get("params", {})

        handlers = {
            "initialize": self.handle_initialize,
            "tools/list": self.handle_list_tools,
            "tools/call": self.handle_call_tool,
        }

        if method not in handlers:
            return {
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}",
                }
            }

        try:
            result = await handlers[method](params)
            return {"result": result}

        except Exception:
            logger.exception(f"Error handling MCP request: {method}")
            return {
                "error": {
                    "code": -32603,
                    "message": "Internal server error",
                }
            }
