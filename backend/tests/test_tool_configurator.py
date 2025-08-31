import asyncio

from models.settings_model import ToolConfig
from utility.tool_configurator import create_configured_tools
from langchain_core.tools import BaseTool
from pydantic import ConfigDict


class FakeTool(BaseTool):
    name: str = "fake_tool"
    description: str = "orig"
    sync_calls: list = []  # for tracking
    async_calls: list = []  # for tracking
    model_config = ConfigDict(extra="allow")

    def __init__(self, description: str = "orig"):
        super().__init__()
        # ensure per-instance lists
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "sync_calls", [])
        object.__setattr__(self, "async_calls", [])

    def _run(self, *args, **kwargs):  # type: ignore[override]
        self.sync_calls.append((args, kwargs))
        return {"result": "sync", "args": args, "kwargs": kwargs}

    async def _arun(self, *args, **kwargs):  # type: ignore[override]
        self.async_calls.append((args, kwargs))
        return {"result": "async", "args": args, "kwargs": kwargs}


def make_tool_config(name: str, enabled: bool = True, prompt_override: str = "") -> ToolConfig:
    return ToolConfig(name=name, enabled=enabled, prompt_override=prompt_override)


def test_disabled_tools_are_filtered_out():
    t1 = FakeTool()
    t2 = FakeTool()

    tools: dict[str, BaseTool] = {"one": t1, "two": t2}  # type: ignore[assignment]
    cfgs = [make_tool_config("one", enabled=True), make_tool_config("two", enabled=False)]

    configured = create_configured_tools(tools, cfgs)

    assert "one" in configured
    assert "two" not in configured


def test_prompt_override_and_sync_wrapper_merges_extras(monkeypatch):
    tool_name = "sync_tool"
    fake = FakeTool(description="original description")

    tools: dict[str, BaseTool] = {tool_name: fake}  # type: ignore[assignment]
    cfg = make_tool_config(tool_name, enabled=True, prompt_override="Custom prompt")

    # Monkeypatch the ToolConfig.model_dump to include extra fields that should be injected
    def fake_model_dump(self):
        return {
            "name": tool_name,
            "enabled": True,
            "prompt_override": "Custom prompt",
            "system_prompt": "SYS",
            "tool_prompt": "TP",
        }

    # Patch at the class level so pydantic doesn't forbid setting instance attributes
    monkeypatch.setattr(ToolConfig, "model_dump", fake_model_dump, raising=False)

    configured = create_configured_tools(tools, [cfg])
    assert tool_name in configured

    wrapped = configured[tool_name]

    # Description should be overridden
    assert getattr(wrapped, "description") == "Custom prompt"

    # Call the wrapped sync run; extras should NOT be merged because _run has no matching params
    result = wrapped._run(1, foo="bar")
    assert result["result"] == "sync"
    # original fake recorded call should include merged keys
    assert fake.sync_calls, "original _run was not called"
    args, kwargs = fake.sync_calls[-1]
    assert kwargs.get("foo") == "bar"
    # extras not injected because parameters absent
    assert "system_prompt" not in kwargs
    assert "tool_prompt" not in kwargs


def test_extras_injected_when_params_exist(monkeypatch):
    class ParamTool(BaseTool):
        name: str = "param_tool"
        description: str = "param"
        model_config = ConfigDict(extra="allow")
        calls: list = []  # tracking

        def __init__(self):  # type: ignore[override]
            super().__init__()
            object.__setattr__(self, "calls", [])

        def _run(self, system_prompt=None, tool_prompt=None, **kwargs):  # type: ignore[override]
            self.calls.append((system_prompt, tool_prompt, kwargs))
            return {"system_prompt": system_prompt, "tool_prompt": tool_prompt, "kwargs": kwargs}

    tool = ParamTool()
    tools: dict[str, BaseTool] = {tool.name: tool}  # type: ignore[assignment]
    cfg = make_tool_config(tool.name, enabled=True, prompt_override="Override")

    def fake_model_dump(self):
        return {
            "name": tool.name,
            "enabled": True,
            "prompt_override": "Override",
            "system_prompt": "SYS",
            "tool_prompt": "TP",
        }

    monkeypatch.setattr(ToolConfig, "model_dump", fake_model_dump, raising=False)
    configured = create_configured_tools(tools, [cfg])
    configured[tool.name]._run()
    system_prompt, tool_prompt, kwargs = tool.calls[-1]
    assert system_prompt == "SYS"
    assert tool_prompt == "TP"


def test_async_wrapper_merges_extras(monkeypatch):
    class AsyncParamTool(BaseTool):
        name: str = "async_param_tool"
        description: str = "async param"
        model_config = ConfigDict(extra="allow")
        calls: list = []

        def __init__(self):
            super().__init__()
            object.__setattr__(self, "calls", [])

        async def _arun(self, extra_flag=False, **kwargs):  # type: ignore[override]
            self.calls.append((extra_flag, kwargs))
            return {"result": "async", "extra_flag": extra_flag, "kwargs": kwargs}

        def _run(self, *args, **kwargs):  # type: ignore[override]
            # Not used in this test
            return {"result": "sync"}

    tool = AsyncParamTool()
    tools: dict[str, BaseTool] = {tool.name: tool}  # type: ignore[assignment]
    cfg = make_tool_config(tool.name, enabled=True, prompt_override="Async Param Prompt")

    def fake_model_dump(self):
        return {
            "name": tool.name,
            "enabled": True,
            "prompt_override": "Async Param Prompt",
            "extra_flag": True,
        }

    monkeypatch.setattr(ToolConfig, "model_dump", fake_model_dump, raising=False)
    configured = create_configured_tools(tools, [cfg])
    coro = configured[tool.name]._arun()
    result = asyncio.run(coro)
    assert result["extra_flag"] is True
    assert tool.calls[-1][0] is True


def test_signature_preserved(monkeypatch):
    """Ensure the original _run signature is unchanged after configuration."""
    import inspect

    tool_name = "sig_tool"
    fake = FakeTool()
    tools: dict[str, BaseTool] = {tool_name: fake}  # type: ignore[assignment]
    cfg = make_tool_config(tool_name, enabled=True)

    original_sig = inspect.signature(fake._run)
    configured = create_configured_tools(tools, [cfg])
    wrapped = configured[tool_name]
    new_sig = inspect.signature(wrapped._run)
    assert original_sig == new_sig


def test_idempotent_configuration(monkeypatch):
    """Calling create_configured_tools twice shouldn't wrap repeatedly or duplicate extras."""
    tool_name = "idempotent_tool"
    fake = FakeTool()
    tools: dict[str, BaseTool] = {tool_name: fake}  # type: ignore[assignment]
    cfg = make_tool_config(tool_name, enabled=True)

    configured1 = create_configured_tools(tools, [cfg])
    configured2 = create_configured_tools(configured1, [cfg])
    # Run tool
    configured2[tool_name]._run(foo=1)
    # Only one call recorded
    assert len(fake.sync_calls) == 1


def test_missing_arun_graceful(monkeypatch):
    """If a tool lacks _arun, configuration should not fail and _run still works."""

    class NoAsyncTool(BaseTool):
        name: str = "no_async_tool"
        description: str = "na"
        calls: list = []  # tracking
        model_config = ConfigDict(extra="allow")

        def __init__(self):
            super().__init__()
            object.__setattr__(self, "calls", [])

        def _run(self, *args, **kwargs):  # type: ignore[override]
            self.calls.append((args, kwargs))
            return {"ok": True}

    tool_name = "no_async"
    t = NoAsyncTool()
    tools: dict[str, BaseTool] = {tool_name: t}  # type: ignore[assignment]
    cfg = make_tool_config(tool_name, enabled=True, prompt_override="New desc")
    configured = create_configured_tools(tools, [cfg])
    configured[tool_name]._run(a=1)
    assert t.calls, "_run not invoked"  # ensure still callable
    assert configured[tool_name].description == "New desc"
