# backend/app/utils/tool_configurator.py
from typing import Callable, Dict, Any, List

from langchain_core.tools import BaseTool
from models.settings_model import ToolConfig
import asyncio


def create_configured_tools(
    tool_functions: Dict[str, BaseTool],
    tool_settings: List[ToolConfig]
) -> Dict[str, BaseTool]:
    """
    Given a dict of BaseTool instances and ToolConfig models,
    returns enabled tools with their _run and _arun methods wrapped to inject prompt_override and extras.
    """
    configured: Dict[str, BaseTool] = {}

    # Map settings by tool name
    settings_map: Dict[str, ToolConfig] = {cfg.name: cfg for cfg in tool_settings}

    for name, tool in tool_functions.items():
        cfg = settings_map.get(name)
        if not cfg or not cfg.enabled:
            continue

        prompt_override = cfg.prompt_override
        extras = {k: v for k, v in cfg.model_dump().items()
                  if k not in ("name", "enabled", "prompt_override")}

        # Create a deep copy of the tool to preserve schema & metadata
        try:
            wrapped_tool = tool.copy(deep=True)
        except Exception:
            # Fallback: instantiate a new tool of same class
            wrapped_tool = tool.__class__(**tool.dict())  # type: ignore

        # Wrap synchronous _run
        original_sync = getattr(wrapped_tool, '_run')

        def make_sync(fn: Callable[..., Any], prompt: str, extra_opts: Dict[str, Any]) -> Callable[..., Any]:
            def wrapped_sync(*args: Any, **kwargs: Any) -> Any:
                local_kwargs = {**kwargs, 'prompt': prompt, **extra_opts}
                return fn(*args, **local_kwargs)
            return wrapped_sync

        wrapped_tool._run = make_sync(original_sync, prompt_override, extras)  # type: ignore

        # Wrap asynchronous _arun if present
        if hasattr(wrapped_tool, '_arun'):
            original_async = getattr(wrapped_tool, '_arun')

            async def wrapped_async(*args: Any, **kwargs: Any) -> Any:
                local_kwargs = {**kwargs, 'prompt': prompt_override, **extras}
                if asyncio.iscoroutinefunction(original_async):
                    return await original_async(*args, **local_kwargs)
                return original_async(*args, **local_kwargs)  # type: ignore
            wrapped_tool._arun = wrapped_async  # type: ignore

        configured[name] = wrapped_tool

    return configured
