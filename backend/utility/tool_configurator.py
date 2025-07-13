from copy import copy
from typing import Dict, Any, List
from models.settings_model import ToolConfig

from langchain_core.runnables import RunnableConfig
from langchain_core.callbacks import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from langchain_core.tools import BaseTool


def create_configured_tools(
    tool_functions: Dict[str, BaseTool],
    tool_settings: List[ToolConfig]
) -> Dict[str, BaseTool]:
    configured: Dict[str, BaseTool] = {}
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

        new_tool = copy(tool)  # avoid mutating the original

        # Override the tool description with the prompt_override
        if prompt_override:
            new_tool.description = prompt_override

        def make_wrapped_sync(original_run):
            def wrapped_sync(*args: Any,
                             config: RunnableConfig,
                             run_manager: CallbackManagerForToolRun = None,
                             **kwargs: Any) -> Any:
                local_kwargs = {**kwargs, **extras}
                return original_run(*args, config=config, run_manager=run_manager, **local_kwargs)
            return wrapped_sync

        def make_wrapped_async(original_arun):
            async def wrapped_async(*args: Any,
                                    config: RunnableConfig,
                                    run_manager: AsyncCallbackManagerForToolRun = None,
                                    **kwargs: Any) -> Any:
                local_kwargs = {**kwargs, **extras}
                return await original_arun(*args, config=config, run_manager=run_manager,
                                           **local_kwargs)
            return wrapped_async

        setattr(new_tool, '_run', make_wrapped_sync(getattr(tool, '_run')))

        if hasattr(tool, '_arun'):
            setattr(new_tool, '_arun', make_wrapped_async(getattr(tool, '_arun')))

        configured[name] = new_tool

    return configured
