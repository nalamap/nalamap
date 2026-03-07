"""
Tests for OGC API server integration with settings and agent construction.
"""

import pytest
from langchain_core.messages import ToolMessage

from models.settings_model import OGCAPIServer, SettingsSnapshot, ToolConfig


def test_ogcapi_server_model():
    server = OGCAPIServer(
        url="http://localhost:8000/v1",
        name="Local OGC",
        description="Test OGC API server",
        enabled=True,
    )
    assert server.url == "http://localhost:8000/v1"
    assert server.name == "Local OGC"
    assert server.enabled is True


def test_ogcapi_server_defaults():
    server = OGCAPIServer(url="http://localhost:8000/v1")
    assert server.enabled is True
    assert server.api_key is None
    assert server.headers is None


def test_settings_snapshot_with_ogcapi_servers():
    snapshot = SettingsSnapshot(
        search_portals=[],
        geoserver_backends=[],
        mcp_servers=[],
        ogcapi_servers=[
            OGCAPIServer(
                url="http://localhost:8000/v1",
                name="Local OGC",
                enabled=True,
            )
        ],
        model_settings={
            "model_provider": "openai",
            "model_name": "gpt-4o-mini",
            "max_tokens": 4096,
            "system_prompt": "",
        },
        tools=[],
    )
    assert len(snapshot.ogcapi_servers) == 1
    assert snapshot.ogcapi_servers[0].url == "http://localhost:8000/v1"


def test_fallback_ogcapi_servers_from_env(monkeypatch):
    import api.nalamap as nalamap_api

    monkeypatch.setattr(nalamap_api.core_config, "USE_OGCAPI_STORAGE", True)
    monkeypatch.setattr(
        nalamap_api.core_config,
        "OGCAPI_PUBLIC_BASE_URL",
        "https://ogc-public.example.com/v1",
    )
    monkeypatch.setattr(
        nalamap_api.core_config,
        "OGCAPI_BASE_URL",
        "http://ogc-internal.example.com/v1",
    )

    servers = nalamap_api._fallback_ogcapi_servers_from_env()
    assert len(servers) == 1
    assert servers[0].url == "https://ogc-public.example.com/v1"
    assert servers[0].enabled is True


def test_resolve_enabled_ogcapi_servers_uses_env_only_when_empty(monkeypatch):
    import api.nalamap as nalamap_api

    monkeypatch.setattr(nalamap_api.core_config, "USE_OGCAPI_STORAGE", True)
    monkeypatch.setattr(
        nalamap_api.core_config,
        "OGCAPI_PUBLIC_BASE_URL",
        "https://ogc-public.example.com/v1",
    )
    monkeypatch.setattr(
        nalamap_api.core_config,
        "OGCAPI_BASE_URL",
        "http://ogc-internal.example.com/v1",
    )

    options = SettingsSnapshot(
        search_portals=[],
        geoserver_backends=[],
        mcp_servers=[],
        ogcapi_servers=[],
        model_settings={
            "model_provider": "openai",
            "model_name": "gpt-4o-mini",
            "max_tokens": 4096,
            "system_prompt": "",
        },
        tools=[],
    )
    enabled = nalamap_api._resolve_enabled_ogcapi_servers(options)
    assert len(enabled) == 1
    assert enabled[0].url == "https://ogc-public.example.com/v1"

    # Explicit user configuration should be respected even if disabled.
    options_with_disabled = SettingsSnapshot(
        search_portals=[],
        geoserver_backends=[],
        mcp_servers=[],
        ogcapi_servers=[
            OGCAPIServer(url="https://manual.example.com/v1", enabled=False),
        ],
        model_settings={
            "model_provider": "openai",
            "model_name": "gpt-4o-mini",
            "max_tokens": 4096,
            "system_prompt": "",
        },
        tools=[],
    )
    enabled_disabled = nalamap_api._resolve_enabled_ogcapi_servers(options_with_disabled)
    assert enabled_disabled == []


def test_env_preconfigured_ogcapi_server_helper(monkeypatch):
    import api.settings as settings_api

    monkeypatch.setattr(settings_api.core_config, "USE_OGCAPI_STORAGE", True)
    monkeypatch.setattr(
        settings_api.core_config,
        "OGCAPI_PUBLIC_BASE_URL",
        "https://ogc-public.example.com/v1",
    )
    monkeypatch.setattr(
        settings_api.core_config,
        "OGCAPI_BASE_URL",
        "http://ogc-internal.example.com/v1",
    )
    server = settings_api._env_preconfigured_ogcapi_server()
    assert server is not None
    assert server.url == "https://ogc-public.example.com/v1"

    monkeypatch.setattr(settings_api.core_config, "USE_OGCAPI_STORAGE", False)
    assert settings_api._env_preconfigured_ogcapi_server() is None


def test_split_query_and_explicit_layer_refs():
    import api.nalamap as nalamap_api

    clean_query, refs = nalamap_api._split_query_and_explicit_layer_refs(
        (
            "buffer with 4km\n\n"
            """
            [EXPLICIT_LAYER_REFS_JSON]
            {
                "layer_refs":
                    [
                        {
                            "id":"layer-1",
                            "name":"points_simple.geojson",
                            "title":"Points"
                        }
                    ]
            }
            [/EXPLICIT_LAYER_REFS_JSON]
            """
        )
    )

    assert clean_query == "buffer with 4km"
    assert "points_simple.geojson" in refs
    assert "Points" in refs
    assert "layer-1" not in refs


def test_split_query_and_explicit_layer_refs_normalizes_prefixed_names():
    import api.nalamap as nalamap_api

    clean_query, refs = nalamap_api._split_query_and_explicit_layer_refs(
        (
            "buffer with 4km\n\n"
            """[EXPLICIT_LAYER_REFS_JSON]
            {
                "layer_refs":
                    [
                        {
                            "id":"48f8cf46100047b7a732e02cb4640501_points_simple.geojson",
                            "name":"points_simple.geojson",
                            "data_source_id":"manual"
                        }
                    ]
            }
            [/EXPLICIT_LAYER_REFS_JSON]"""
        )
    )

    assert clean_query == "buffer with 4km"
    assert refs == ["points_simple.geojson"]


def test_extract_ogcapi_result_urls_dedupes_sources():
    import api.nalamap as nalamap_api

    url = "http://localhost:8081/v1/processes/vector-buffer/jobs/job-1/results"
    messages = [
        ToolMessage(
            content=f'{{"status":"ok","job_results_url":"{url}"}}',
            tool_call_id="tool-1",
            name="process_geodata",
        )
    ]
    geodata_results = [{"data_link": url}]

    urls = nalamap_api._extract_ogcapi_result_urls(messages, geodata_results)
    assert urls == [url]


def test_extract_ogcapi_result_urls_ignores_non_process_links():
    import api.nalamap as nalamap_api

    messages = [
        ToolMessage(
            content='{"status":"ok","job_results_url":"http://localhost:8081/v1/collections/foo/items"}',
            tool_call_id="tool-1",
            name="process_geodata",
        )
    ]
    geodata_results = [{"data_link": "http://localhost:8081/v1/collections/foo/items"}]

    urls = nalamap_api._extract_ogcapi_result_urls(messages, geodata_results)
    assert urls == []


@pytest.mark.asyncio
async def test_create_geo_agent_with_ogcapi_servers(monkeypatch):
    from services.single_agent import create_geo_agent

    class DummyLLM:
        def bind_tools(self, tools, parallel_tool_calls=False):
            return self

    ogc_tools_loaded = {}

    def fake_build_ogcapi_tools(ogcapi_servers, default_session_id=None, **kwargs):
        ogc_tools_loaded["count"] = len(ogcapi_servers)
        ogc_tools_loaded["session_id"] = default_session_id
        ogc_tools_loaded["include_prepare"] = kwargs.get("include_prepare")
        ogc_tools_loaded["include_filter"] = kwargs.get("include_filter")
        ogc_tools_loaded["include_process"] = kwargs.get("include_process")
        return []

    def fake_create_react_agent(**kwargs):
        return {"agent": "fake", "tools_count": len(kwargs.get("tools", []))}

    monkeypatch.setattr("services.single_agent.get_llm", lambda: DummyLLM())
    monkeypatch.setattr("services.single_agent.create_react_agent", fake_create_react_agent)
    monkeypatch.setattr("services.single_agent.build_ogcapi_tools", fake_build_ogcapi_tools)

    ogcapi_servers = [OGCAPIServer(url="http://localhost:8000/v1", enabled=True)]

    agent, _llm = await create_geo_agent(
        selected_tools=[],
        session_id="test-ogcapi-session",
        ogcapi_servers=ogcapi_servers,
    )

    assert agent is not None
    assert ogc_tools_loaded["count"] == 1
    assert ogc_tools_loaded["session_id"] == "test-ogcapi-session"
    assert ogc_tools_loaded["include_prepare"] is True
    assert ogc_tools_loaded["include_filter"] is True
    assert ogc_tools_loaded["include_process"] is True


@pytest.mark.asyncio
async def test_create_geo_agent_respects_ogc_tool_toggles(monkeypatch):
    from services.single_agent import create_geo_agent

    class DummyLLM:
        def bind_tools(self, tools, parallel_tool_calls=False):
            return self

    ogc_tools_loaded = {}

    def fake_build_ogcapi_tools(ogcapi_servers, default_session_id=None, **kwargs):
        ogc_tools_loaded["count"] = len(ogcapi_servers)
        ogc_tools_loaded["session_id"] = default_session_id
        ogc_tools_loaded["include_prepare"] = kwargs.get("include_prepare")
        ogc_tools_loaded["include_filter"] = kwargs.get("include_filter")
        ogc_tools_loaded["include_process"] = kwargs.get("include_process")
        return []

    def fake_create_react_agent(**kwargs):
        return {"agent": "fake", "tools_count": len(kwargs.get("tools", []))}

    monkeypatch.setattr("services.single_agent.get_llm", lambda: DummyLLM())
    monkeypatch.setattr("services.single_agent.create_react_agent", fake_create_react_agent)
    monkeypatch.setattr("services.single_agent.build_ogcapi_tools", fake_build_ogcapi_tools)

    ogcapi_servers = [OGCAPIServer(url="http://localhost:8000/v1", enabled=True)]

    selected_tools = [
        ToolConfig(name="filter_geodata", enabled=False, prompt_override=""),
        ToolConfig(name="process_geodata", enabled=False, prompt_override=""),
    ]

    agent, _llm = await create_geo_agent(
        selected_tools=selected_tools,
        session_id="test-ogcapi-session",
        ogcapi_servers=ogcapi_servers,
    )

    assert agent is not None
    assert ogc_tools_loaded["count"] == 1
    assert ogc_tools_loaded["session_id"] == "test-ogcapi-session"
    assert ogc_tools_loaded["include_prepare"] is False
    assert ogc_tools_loaded["include_filter"] is False
    assert ogc_tools_loaded["include_process"] is False


@pytest.mark.asyncio
async def test_create_geo_agent_prefers_ogc_process_over_legacy_geoprocess(monkeypatch):
    from services.single_agent import create_geo_agent

    class DummyLLM:
        def bind_tools(self, tools, parallel_tool_calls=False):
            return self

    captured = {}

    class DummyOGCTool:
        name = "process_geodata"

    def fake_build_ogcapi_tools(ogcapi_servers, default_session_id=None, **kwargs):
        return [DummyOGCTool()]

    def fake_create_react_agent(**kwargs):
        captured["tool_names"] = [getattr(t, "name", "") for t in kwargs.get("tools", [])]
        return {"agent": "fake"}

    monkeypatch.setattr("services.single_agent.get_llm", lambda: DummyLLM())
    monkeypatch.setattr("services.single_agent.create_react_agent", fake_create_react_agent)
    monkeypatch.setattr("services.single_agent.build_ogcapi_tools", fake_build_ogcapi_tools)

    ogcapi_servers = [OGCAPIServer(url="http://localhost:8000/v1", enabled=True)]
    selected_tools = [ToolConfig(name="geoprocess", enabled=True, prompt_override="")]

    agent, _llm = await create_geo_agent(
        selected_tools=selected_tools,
        session_id="test-ogcapi-session",
        ogcapi_servers=ogcapi_servers,
    )

    assert agent is not None
    assert "process_geodata" in captured["tool_names"]
    assert "geoprocess_tool" not in captured["tool_names"]


@pytest.mark.asyncio
async def test_create_geo_agent_does_not_force_required_tool_choice_for_ogc_geoprocess_query(
    monkeypatch,
):
    from services.single_agent import create_geo_agent

    captured = {}

    class DummyLLM:
        def bind_tools(self, tools, parallel_tool_calls=False, **kwargs):
            captured["tool_choice"] = kwargs.get("tool_choice")
            return self

    class DummyOGCTool:
        name = "process_geodata"

    def fake_build_ogcapi_tools(ogcapi_servers, default_session_id=None, **kwargs):
        return [DummyOGCTool()]

    def fake_create_react_agent(**kwargs):
        return {"agent": "fake", "tools_count": len(kwargs.get("tools", []))}

    monkeypatch.setattr("services.single_agent.get_llm", lambda: DummyLLM())
    monkeypatch.setattr("services.single_agent.create_react_agent", fake_create_react_agent)
    monkeypatch.setattr("services.single_agent.build_ogcapi_tools", fake_build_ogcapi_tools)

    ogcapi_servers = [OGCAPIServer(url="http://localhost:8000/v1", enabled=True)]
    selected_tools = [ToolConfig(name="process_geodata", enabled=True, prompt_override="")]

    agent, _llm = await create_geo_agent(
        selected_tools=selected_tools,
        query="buffer selected layer by 4 km",
        session_id="test-ogcapi-session",
        ogcapi_servers=ogcapi_servers,
    )

    assert agent is not None
    assert captured.get("tool_choice") is None


@pytest.mark.asyncio
async def test_create_geo_agent_uses_env_fallback_when_ogcapi_servers_none(monkeypatch):
    from services.single_agent import create_geo_agent

    class DummyLLM:
        def bind_tools(self, tools, parallel_tool_calls=False, **kwargs):
            return self

    captured = {}

    def fake_build_ogcapi_tools(ogcapi_servers, default_session_id=None, **kwargs):
        captured["server_count"] = len(ogcapi_servers)
        captured["first_url"] = ogcapi_servers[0].url if ogcapi_servers else None
        return []

    def fake_create_react_agent(**kwargs):
        return {"agent": "fake"}

    monkeypatch.setattr("services.single_agent.get_llm", lambda: DummyLLM())
    monkeypatch.setattr("services.single_agent.create_react_agent", fake_create_react_agent)
    monkeypatch.setattr("services.single_agent.build_ogcapi_tools", fake_build_ogcapi_tools)
    monkeypatch.setattr("services.single_agent.core_config.USE_OGCAPI_STORAGE", True)
    monkeypatch.setattr(
        "services.single_agent.core_config.OGCAPI_PUBLIC_BASE_URL",
        "https://ogc-public.example.com/v1",
    )
    monkeypatch.setattr(
        "services.single_agent.core_config.OGCAPI_BASE_URL",
        "http://ogc-internal.example.com/v1",
    )

    agent, _llm = await create_geo_agent(selected_tools=[], session_id="test-ogc-fallback")

    assert agent is not None
    assert captured["server_count"] == 1
    assert captured["first_url"] == "https://ogc-public.example.com/v1"


@pytest.mark.asyncio
async def test_create_geo_agent_does_not_fallback_when_explicit_ogcapi_empty_and_ogc_tools_disabled(
    monkeypatch,
):
    from services.single_agent import create_geo_agent

    class DummyLLM:
        def bind_tools(self, tools, parallel_tool_calls=False, **kwargs):
            return self

    called = {"ogc": False}

    def fake_build_ogcapi_tools(ogcapi_servers, default_session_id=None, **kwargs):
        called["ogc"] = True
        return []

    def fake_create_react_agent(**kwargs):
        return {"agent": "fake"}

    monkeypatch.setattr("services.single_agent.get_llm", lambda: DummyLLM())
    monkeypatch.setattr("services.single_agent.create_react_agent", fake_create_react_agent)
    monkeypatch.setattr("services.single_agent.build_ogcapi_tools", fake_build_ogcapi_tools)
    monkeypatch.setattr("services.single_agent.core_config.USE_OGCAPI_STORAGE", True)
    monkeypatch.setattr(
        "services.single_agent.core_config.OGCAPI_PUBLIC_BASE_URL",
        "https://ogc-public.example.com/v1",
    )

    selected_tools = [
        ToolConfig(name="filter_geodata", enabled=False, prompt_override=""),
        ToolConfig(name="process_geodata", enabled=False, prompt_override=""),
    ]

    agent, _llm = await create_geo_agent(
        selected_tools=selected_tools,
        session_id="test-ogc-no-fallback",
        ogcapi_servers=[],
    )

    assert agent is not None
    assert called["ogc"] is False


@pytest.mark.asyncio
async def test_create_geo_agent_fallbacks_when_explicit_ogcapi_empty_but_ogc_tools_enabled(
    monkeypatch,
):
    from services.single_agent import create_geo_agent

    class DummyLLM:
        def bind_tools(self, tools, parallel_tool_calls=False, **kwargs):
            return self

    captured = {}

    def fake_build_ogcapi_tools(ogcapi_servers, default_session_id=None, **kwargs):
        captured["server_count"] = len(ogcapi_servers)
        captured["first_url"] = ogcapi_servers[0].url if ogcapi_servers else None
        return []

    def fake_create_react_agent(**kwargs):
        return {"agent": "fake"}

    monkeypatch.setattr("services.single_agent.get_llm", lambda: DummyLLM())
    monkeypatch.setattr("services.single_agent.create_react_agent", fake_create_react_agent)
    monkeypatch.setattr("services.single_agent.build_ogcapi_tools", fake_build_ogcapi_tools)
    monkeypatch.setattr("services.single_agent.core_config.USE_OGCAPI_STORAGE", False)
    monkeypatch.setattr(
        "services.single_agent.core_config.OGCAPI_PUBLIC_BASE_URL",
        "https://ogc-public.example.com/v1",
    )

    selected_tools = [ToolConfig(name="process_geodata", enabled=True, prompt_override="")]
    agent, _llm = await create_geo_agent(
        selected_tools=selected_tools,
        session_id="test-ogc-empty-enabled",
        ogcapi_servers=[],
    )

    assert agent is not None
    assert captured["server_count"] == 1
    assert captured["first_url"] == "https://ogc-public.example.com/v1"
