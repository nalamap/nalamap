import copy
from typing import Dict, Any, List

from langchain_core.tools import BaseTool
from models.settings_model import ToolConfig


def create_configured_tools(
    tool_functions: Dict[str, BaseTool],
    tool_settings: List[ToolConfig]
) -> Dict[str, BaseTool]:
    """
    Given a dict of BaseTool instances and a list of ToolConfig models,
    returns enabled tools with their internal _run/_arun methods wrapped to inject prompt_override and extras.

    Ensures returned objects are BaseTool instances (valid Pydantic) so the agent can register them correctly.
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
            k: v for k, v in cfg.model_dump().items()
            if k not in ('name', 'enabled', 'prompt_override')
        }

        # Create a shallow copy to avoid mutating the original
        new_tool: BaseTool = copy.copy(tool)

        # Wrap synchronous _run
        original_run = getattr(new_tool, '_run')

        def wrapped_sync(*args: Any, **kwargs: Any) -> Any:
            local_kwargs = {**kwargs, 'prompt': prompt_override, **extras}
            return original_run(*args, **local_kwargs)
        setattr(new_tool, '_run', wrapped_sync)  # type: ignore

        # Wrap asynchronous _arun if present
        if hasattr(new_tool, '_arun'):
            original_arun = getattr(new_tool, '_arun')

            async def wrapped_async(*args: Any, **kwargs: Any) -> Any:
                local_kwargs = {**kwargs, 'prompt': prompt_override, **extras}
                return await original_arun(*args, **local_kwargs)
            setattr(new_tool, '_arun', wrapped_async)  # type: ignore

        configured[name] = new_tool

    return configured
