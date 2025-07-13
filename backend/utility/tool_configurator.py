# backend/app/utils/tool_configurator.py
from typing import Dict, Any, List

from langchain_core.tools import BaseTool
from models.settings_model import ToolConfig


def create_configured_tools(
    tool_functions: Dict[str, BaseTool],
    tool_settings: List[ToolConfig]
) -> Dict[str, BaseTool]:
    """
    Given a dict of BaseTool instances and a list of ToolConfig models,
    returns enabled tools with their _run and _arun methods wrapped to inject prompt_override and extras.
    """
    configured: Dict[str, BaseTool] = {}

    # Map ToolConfig by tool name
    settings_map = {cfg.name: cfg for cfg in tool_settings}

    for name, tool in tool_functions.items():
        cfg = settings_map.get(name)
        if not cfg or not cfg.enabled:
            continue

        prompt_override = cfg.prompt_override
        extras = {
            k: v for k, v in cfg.dict().items()
            if k not in ('name', 'enabled', 'prompt_override')
        }

        # Wrap sync _run
        original_run = tool._run  # type: ignore

        def wrapped_sync(*args: Any, **kwargs: Any) -> Any:
            local_kwargs = {**kwargs, 'prompt': prompt_override, **extras}
            return original_run(*args, **local_kwargs)

        # Prepare updates dict for Pydantic copy
        updates: Dict[str, Any] = {'_run': wrapped_sync}

        # Wrap async _arun if exists
        if hasattr(tool, '_arun'):
            original_arun = tool._arun  # type: ignore
            
            async def wrapped_async(*args: Any, **kwargs: Any) -> Any:
                local_kwargs = {**kwargs, 'prompt': prompt_override, **extras}
                return await original_arun(*args, **local_kwargs)
            updates['_arun'] = wrapped_async

        # Create a deep copy with overridden run methods
        wrapped_tool = tool.copy(deep=True).copy(update=updates)  # type: ignore

        configured[name] = wrapped_tool

    return configured
