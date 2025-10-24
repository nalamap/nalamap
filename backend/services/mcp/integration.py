"""Integration layer for using MCP tools with LangChain agents."""

import asyncio
import logging
from typing import Any, Dict, Optional, Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, create_model

from services.mcp.client import MCPClient

logger = logging.getLogger(__name__)


class MCPToolWrapper(BaseTool):
    """Wrapper to use MCP tools as LangChain tools.

    Bridges external MCP tools into LangChain's tool framework,
    allowing NaLaMap agents to seamlessly use external tools.
    """

    name: str
    description: str
    mcp_client: MCPClient
    tool_name: str
    args_schema: Optional[Type[BaseModel]] = None

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True

    def _run(self, **kwargs) -> Any:
        """Execute MCP tool (sync wrapper).

        Args:
            **kwargs: Tool arguments

        Returns:
            Tool execution result
        """
        return asyncio.run(self._arun(**kwargs))

    async def _arun(self, **kwargs) -> Any:
        """Execute MCP tool (async).

        Args:
            **kwargs: Tool arguments

        Returns:
            Tool execution result
        """
        try:
            result = await self.mcp_client.call_tool(self.tool_name, kwargs)
            return result
        except Exception as e:
            logger.error(f"Error calling MCP tool {self.tool_name}: {e}")
            return f"Error: {str(e)}"


def _create_args_schema_from_mcp(tool_name: str, input_schema: Dict[str, Any]) -> Type[BaseModel]:
    """Create Pydantic model from MCP input schema.

    Args:
        tool_name: Name of the tool (for model name)
        input_schema: MCP JSON schema for tool inputs

    Returns:
        Pydantic model class
    """
    properties = input_schema.get("properties", {})
    required = set(input_schema.get("required", []))

    # Convert JSON schema properties to Pydantic fields
    field_definitions = {}
    for prop_name, prop_schema in properties.items():
        prop_type = prop_schema.get("type", "string")
        prop_description = prop_schema.get("description", "")
        prop_default = prop_schema.get("default")

        # Map JSON schema types to Python types
        type_mapping = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict,
        }

        python_type = type_mapping.get(prop_type, str)

        # Make optional if not required
        if prop_name not in required:
            if prop_default is not None:
                field_definitions[prop_name] = (
                    python_type,
                    Field(default=prop_default, description=prop_description),
                )
            else:
                field_definitions[prop_name] = (
                    Optional[python_type],
                    Field(default=None, description=prop_description),
                )
        else:
            field_definitions[prop_name] = (
                python_type,
                Field(description=prop_description),
            )

    # Create dynamic model
    model_name = f"{tool_name.replace('-', '_').replace(' ', '_')}Input"
    return create_model(model_name, **field_definitions)


async def load_mcp_tools(
    server_url: str,
    api_key: Optional[str] = None,
    headers: Optional[dict] = None,
) -> list[BaseTool]:
    """Load tools from an MCP server as LangChain tools.

    Args:
        server_url: URL of the MCP server
        api_key: Optional API key for authentication
        headers: Optional custom headers for authentication

    Returns:
        List of LangChain-compatible tool wrappers

    Raises:
        Exception: If connection or tool loading fails
    """
    client = MCPClient(server_url, api_key=api_key, headers=headers)

    try:
        await client.initialize()

        tools = []
        for tool_info in client.available_tools:
            tool_name = tool_info["name"]
            tool_description = tool_info["description"]
            input_schema = tool_info.get("inputSchema", {})

            # Create args schema from MCP schema
            args_schema = _create_args_schema_from_mcp(tool_name, input_schema)

            # Create wrapper
            tool = MCPToolWrapper(
                name=tool_name,
                description=tool_description,
                mcp_client=client,
                tool_name=tool_name,
                args_schema=args_schema,
            )
            tools.append(tool)

        logger.info(f"Loaded {len(tools)} tools from MCP server: {server_url}")

        return tools

    except Exception as e:
        logger.error(f"Failed to load MCP tools from {server_url}: {e}")
        await client.close()
        raise
