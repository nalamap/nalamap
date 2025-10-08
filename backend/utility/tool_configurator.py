"""Tool configurator that preserves original BaseTool instances.

Strategy:
  * Return only enabled tools.
  * Apply prompt_override by setting the tool.description (does not alter schema).
  * (Future) Extras: merge static config values into runtime kwargs without
    changing the public signature to keep LangChain's binder happy.
  * Avoid wrapping with new callables to prevent docstring/signature mismatch
    errors like: "Arg state in docstring not found in function signature.".
"""

import functools
import inspect
import logging
from typing import Any, Dict, List

from langchain_core.tools import BaseTool

from models.settings_model import ToolConfig

logger = logging.getLogger(__name__)


def _attach_extras(tool: BaseTool, extras: Dict[str, Any]):
    """Patch the tool's _run and _arun to inject extras as default kwargs.

    We do NOT modify the signature; we only add missing kwargs at runtime.
    Only keys that are parameters of the underlying function are applied to
    avoid unexpected argument errors.
    """

    if not extras:
        return

    # Underlying callable for sync
    run_attr = getattr(tool, "_run", None)
    if run_attr and callable(run_attr):
        try:
            sig = inspect.signature(run_attr)
            valid_names = set(sig.parameters.keys())
        except Exception:
            valid_names = set()

        @functools.wraps(run_attr)
        def patched_run(*args, **kwargs):
            for k, v in extras.items():
                if k in valid_names and k not in kwargs:
                    kwargs[k] = v
            return run_attr(*args, **kwargs)

        tool._run = patched_run  # type: ignore

    # Async variant
    arun_attr = getattr(tool, "_arun", None)
    if arun_attr and callable(arun_attr):
        try:
            asig = inspect.signature(arun_attr)
            aval = set(asig.parameters.keys())
        except Exception:
            aval = set()

        try:
            is_coroutine = inspect.iscoroutinefunction(arun_attr)
        except Exception:
            is_coroutine = False

        if is_coroutine:

            @functools.wraps(arun_attr)
            async def patched_arun_async(*args, **kwargs):
                for k, v in extras.items():
                    if k in aval and k not in kwargs:
                        kwargs[k] = v
                return await arun_attr(*args, **kwargs)

            try:
                tool._arun = patched_arun_async  # type: ignore
            except Exception:
                logger.debug(
                    "Could not patch coroutine _arun for tool %s", getattr(tool, "name", "unknown")
                )
        else:  # Graceful: treat as sync fallback executed in async context

            @functools.wraps(arun_attr)
            async def patched_arun_sync_wrapper(*args, **kwargs):  # type: ignore
                for k, v in extras.items():
                    if k in aval and k not in kwargs:
                        kwargs[k] = v
                return arun_attr(*args, **kwargs)

            try:
                tool._arun = patched_arun_sync_wrapper  # type: ignore
            except Exception:
                logger.debug(
                    "Could not patch sync-as-async _arun for tool %s",
                    getattr(tool, "name", "unknown"),
                )

    # Keep a reference for debugging
    setattr(tool, "config_extras", extras)


def create_configured_tools(
    tool_functions: Dict[str, BaseTool], tool_settings: List[ToolConfig]
) -> Dict[str, BaseTool]:
    if not tool_settings:
        # Nothing overridden; return originals
        return tool_functions

    settings_map = {cfg.name: cfg for cfg in tool_settings}
    configured: Dict[str, BaseTool] = {}

    for name, tool in tool_functions.items():
        cfg = settings_map.get(name)
        if not cfg or not cfg.enabled:
            continue

        # Apply prompt override
        if cfg.prompt_override:
            try:
                tool.description = cfg.prompt_override  # type: ignore
            except Exception:
                logger.debug("Failed to set description for tool %s", name)

        # Extract extras (future extension fields beyond current schema)
        extras = {
            k: v
            for k, v in cfg.model_dump().items()
            if k not in ("name", "enabled", "prompt_override") and v is not None
        }
        if extras:
            _attach_extras(tool, extras)

        configured[name] = tool

    return configured
