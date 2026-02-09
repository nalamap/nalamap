"""
Tests for MCP server integration with settings and agent.
"""

import pytest
from models.settings_model import MCPServer, SettingsSnapshot


def test_mcp_server_model():
    """Test MCPServer model creation and validation."""
    server = MCPServer(
        url="http://localhost:8001/mcp",
        name="Test Server",
        description="A test MCP server",
        enabled=True,
    )
    assert server.url == "http://localhost:8001/mcp"
    assert server.name == "Test Server"
    assert server.description == "A test MCP server"
    assert server.enabled is True


def test_mcp_server_defaults():
    """Test MCPServer model with default values."""
    server = MCPServer(url="http://localhost:8001/mcp")
    assert server.url == "http://localhost:8001/mcp"
    assert server.name is None
    assert server.description is None
    assert server.enabled is True


def test_settings_snapshot_with_mcp_servers():
    """Test SettingsSnapshot includes mcp_servers field."""
    snapshot = SettingsSnapshot(
        search_portals=[],
        geoserver_backends=[],
        mcp_servers=[
            MCPServer(
                url="http://localhost:8001/mcp",
                name="Test Server",
                description="Test",
                enabled=True,
            )
        ],
        model_settings={
            "model_provider": "openai",
            "model_name": "gpt-4o-mini",
            "max_tokens": 4000,
            "system_prompt": "",
        },
        tools=[],
    )
    assert len(snapshot.mcp_servers) == 1
    assert snapshot.mcp_servers[0].url == "http://localhost:8001/mcp"
    assert snapshot.mcp_servers[0].enabled is True


def test_settings_snapshot_with_empty_mcp_servers():
    """Test SettingsSnapshot with no MCP servers (default)."""
    snapshot = SettingsSnapshot(
        search_portals=[],
        geoserver_backends=[],
        model_settings={
            "model_provider": "openai",
            "model_name": "gpt-4o-mini",
            "max_tokens": 4000,
            "system_prompt": "",
        },
        tools=[],
    )
    assert snapshot.mcp_servers == []


def test_mcp_server_serialization():
    """Test MCPServer can be serialized to dict."""
    server = MCPServer(
        url="http://localhost:8001/mcp",
        name="Test Server",
        description="A test server",
        enabled=False,
    )
    data = server.model_dump()
    assert data["url"] == "http://localhost:8001/mcp"
    assert data["name"] == "Test Server"
    assert data["description"] == "A test server"
    assert data["enabled"] is False


@pytest.mark.asyncio
async def test_create_geo_agent_with_mcp_servers(monkeypatch):
    """Test that create_geo_agent accepts and processes MCP servers."""
    from services.single_agent import create_geo_agent
    from models.settings_model import MCPServer

    # Mock the MCP integration to avoid actual server connections
    mcp_tools_loaded = []

    async def mock_load_mcp_tools(server_url, api_key=None, headers=None):
        """Mock MCP tool loading."""
        mcp_tools_loaded.append((server_url, api_key, headers))
        # Return empty list (no actual tools)
        return []

    # Patch the load_mcp_tools function
    monkeypatch.setattr("services.mcp.integration.load_mcp_tools", mock_load_mcp_tools)

    # Create agent with MCP servers
    mcp_servers = [
        MCPServer(url="http://localhost:8001/mcp", enabled=True),
        MCPServer(
            url="http://localhost:8002/mcp",
            enabled=True,
            api_key="test-key",
        ),
    ]

    agent, llm = await create_geo_agent(
        selected_tools=[],
        session_id="test-session",
        mcp_servers=mcp_servers,
    )

    # Verify agent was created
    assert agent is not None

    # Verify MCP tools were attempted to be loaded
    assert len(mcp_tools_loaded) == 2
    assert mcp_tools_loaded[0][0] == "http://localhost:8001/mcp"
    assert mcp_tools_loaded[0][1] is None  # No API key
    assert mcp_tools_loaded[1][0] == "http://localhost:8002/mcp"
    assert mcp_tools_loaded[1][1] == "test-key"  # Has API key


@pytest.mark.asyncio
async def test_create_geo_agent_with_no_mcp_servers():
    """Test that create_geo_agent works without MCP servers (backward compatibility)."""
    from services.single_agent import create_geo_agent

    # Create agent without MCP servers
    agent = await create_geo_agent(
        selected_tools=[],
        session_id="test-session",
        mcp_servers=None,
    )

    # Verify agent was created
    assert agent is not None


@pytest.mark.asyncio
async def test_create_geo_agent_with_empty_mcp_servers():
    """Test that create_geo_agent works with empty MCP server list."""
    from services.single_agent import create_geo_agent

    # Create agent with empty MCP server list
    agent = await create_geo_agent(
        selected_tools=[],
        session_id="test-session",
        mcp_servers=[],
    )

    # Verify agent was created
    assert agent is not None
