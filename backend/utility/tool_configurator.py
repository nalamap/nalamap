from copy import copy
from typing import Dict, Any, List
from models.settings_model import ToolConfig

from langchain_core.runnables import RunnableConfig
from langchain_core.callbacks import AsyncCallbackManagerForToolRun, CallbackManagerForToolRun
from langchain_core.tools import BaseTool


def create_configured_tools(tool_functions: Dict[str, BaseTool],
                            tool_settings: List[ToolConfig]) -> Dict[str, BaseTool]:
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
        original_run = getattr(new_tool, '_run')

        def wrapped_sync(*args: Any,
                         config: RunnableConfig = None,
                         run_manager: CallbackManagerForToolRun = None,
                         **kwargs: Any) -> Any:
            # Merge extra kwargs and override prompt
            local_kwargs = {**kwargs, **extras, 'prompt': prompt_override}
            # Call original _run with all arguments, including config and run_manager
            return original_run(*args, config=config, run_manager=run_manager, **local_kwargs)
        setattr(new_tool, '_run', wrapped_sync)

        # If the tool supports async, wrap _arun similarly
        if hasattr(new_tool, '_arun'):
            original_arun = getattr(new_tool, '_arun')

            async def wrapped_async(*args: Any,
                                    config: RunnableConfig = None,
                                    run_manager: AsyncCallbackManagerForToolRun = None,
                                    **kwargs: Any) -> Any:
                local_kwargs = {**kwargs, **extras, 'prompt': prompt_override}
                return await original_arun(*args, config=config, run_manager=run_manager,
                                           **local_kwargs)
            setattr(new_tool, '_arun', wrapped_async)

        configured[name] = new_tool
    return configured
