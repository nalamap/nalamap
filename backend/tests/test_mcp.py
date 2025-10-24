"""Tests for MCP (Model Context Protocol) implementation."""

import pytest
from fastapi.testclient import TestClient

from main import app
from services.mcp.server import MCPServer


@pytest.mark.mcp
class TestMCPServer:
    """Tests for MCP server core functionality."""

    @pytest.mark.asyncio
    async def test_server_initialization(self):
        """Test MCP server initializes with tools."""
        server = MCPServer()

        assert server.name == "nalamap-mcp-server"
        assert server.PROTOCOL_VERSION == "2024-11-05"
        assert len(server.tools) > 0  # Should have registered tools

    @pytest.mark.asyncio
    async def test_handle_initialize(self):
        """Test MCP initialize request."""
        server = MCPServer()
        response = await server.handle_initialize({})

        assert "protocolVersion" in response
        assert response["protocolVersion"] == "2024-11-05"
        assert "capabilities" in response
        assert "serverInfo" in response
        assert response["serverInfo"]["name"] == "nalamap-mcp-server"

    @pytest.mark.asyncio
    async def test_handle_list_tools(self):
        """Test listing available tools."""
        server = MCPServer()
        response = await server.handle_list_tools()

        assert "tools" in response
        assert len(response["tools"]) > 0

        # Check tool structure
        tool = response["tools"][0]
        assert "name" in tool
        assert "description" in tool
        assert "inputSchema" in tool

    @pytest.mark.asyncio
    async def test_registered_tools(self):
        """Test specific tools are registered."""
        server = MCPServer()
        response = await server.handle_list_tools()

        tool_names = [tool["name"] for tool in response["tools"]]

        # Check key tools are present
        assert "geocode_location" in tool_names
        assert "find_pois" in tool_names
        assert "geoprocess" in tool_names
        assert "style_layer" in tool_names
        assert "analyze_attributes" in tool_names

    @pytest.mark.asyncio
    async def test_handle_unknown_method(self):
        """Test handling of unknown MCP method."""
        server = MCPServer()
        request = {
            "method": "unknown/method",
            "params": {},
        }

        response = await server.handle_request(request)

        assert "error" in response
        assert response["error"]["code"] == -32601
        assert "Method not found" in response["error"]["message"]

    @pytest.mark.asyncio
    async def test_call_unknown_tool(self):
        """Test calling non-existent tool returns error."""
        server = MCPServer()

        response = await server.handle_call_tool({"name": "nonexistent_tool", "arguments": {}})

        assert response["isError"] is True
        assert "Unknown tool" in response["content"][0]["text"]


@pytest.mark.mcp
class TestMCPAPI:
    """Tests for MCP HTTP API endpoints."""

    def setup_method(self):
        """Set up test client."""
        self.client = TestClient(app)

    def test_mcp_info_endpoint(self):
        """Test GET /api/mcp/ returns server info."""
        response = self.client.get("/api/mcp/")

        assert response.status_code == 200
        data = response.json()

        assert data["protocol"] == "MCP"
        assert data["transport"] == "http"
        assert data["endpoint"] == "/api/mcp"
        assert "tools_count" in data

    def test_list_tools_endpoint(self):
        """Test GET /api/mcp/tools lists tools."""
        response = self.client.get("/api/mcp/tools")

        assert response.status_code == 200
        tools = response.json()

        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_mcp_initialize_request(self):
        """Test POST /api/mcp/ with initialize request."""
        request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {
                    "name": "test-client",
                    "version": "1.0.0",
                },
            },
        }

        response = self.client.post("/api/mcp/", json=request)

        assert response.status_code == 200
        data = response.json()

        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 1
        assert "result" in data
        assert "protocolVersion" in data["result"]

    def test_mcp_list_tools_request(self):
        """Test POST /api/mcp/ with tools/list request."""
        request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }

        response = self.client.post("/api/mcp/", json=request)

        assert response.status_code == 200
        data = response.json()

        assert data["jsonrpc"] == "2.0"
        assert data["id"] == 2
        assert "result" in data
        assert "tools" in data["result"]

    def test_mcp_invalid_json(self):
        """Test POST /api/mcp/ with invalid JSON."""
        response = self.client.post(
            "/api/mcp/",
            content="invalid json",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 500


@pytest.mark.mcp
@pytest.mark.integration
class TestMCPIntegration:
    """Integration tests for MCP functionality."""

    def setup_method(self):
        """Set up test client."""
        self.client = TestClient(app)

    def test_full_mcp_workflow(self):
        """Test complete MCP workflow: initialize -> list tools -> call tool."""
        # 1. Initialize
        init_request = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        }

        response = self.client.post("/api/mcp/", json=init_request)
        assert response.status_code == 200
        assert "result" in response.json()

        # 2. List tools
        list_request = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }

        response = self.client.post("/api/mcp/", json=list_request)
        assert response.status_code == 200
        data = response.json()
        assert len(data["result"]["tools"]) > 0

        # 3. Verify tool schemas
        tools = data["result"]["tools"]
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool
            assert "type" in tool["inputSchema"]
            assert "properties" in tool["inputSchema"]


@pytest.mark.mcp
@pytest.mark.unit
class TestMCPToolSchema:
    """Tests for MCP tool schema extraction."""

    @pytest.mark.asyncio
    async def test_tool_schema_structure(self):
        """Test tool schemas have correct structure."""
        server = MCPServer()
        response = await server.handle_list_tools()

        for tool in response["tools"]:
            schema = tool["inputSchema"]

            # Check schema structure
            assert schema["type"] == "object"
            assert "properties" in schema

            # Properties should be a dict
            assert isinstance(schema["properties"], dict)

            # Required should be a list (can be empty)
            required = schema.get("required", [])
            assert isinstance(required, list)


@pytest.mark.mcp
@pytest.mark.unit
class TestMCPErrorHandling:
    """Tests for MCP error handling."""

    @pytest.mark.asyncio
    async def test_handle_request_error(self):
        """Test error handling in handle_request."""
        server = MCPServer()

        # Test with invalid method
        request = {"method": "invalid/method", "params": {}}

        response = await server.handle_request(request)

        assert "error" in response
        assert "code" in response["error"]
        assert "message" in response["error"]

    def test_api_error_handling(self):
        """Test API error handling."""
        client = TestClient(app)

        # Test with malformed request
        response = client.post("/api/mcp/", json={})

        # Should return error or handle gracefully
        assert response.status_code in [200, 400, 500]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
