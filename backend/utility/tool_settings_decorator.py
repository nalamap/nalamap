from typing import Any, Dict, List
import inspect
from langchain_core.tools import tool, BaseTool
from fastapi import Depends, Request
from utility.tool_settings_decorator import get_agent_session, AgentSession

OptionDef = Dict[str, Any]  # { key, type, label, default, options? }


def tool_with_schema(
    name: str,
    default_prompt: str,
    schema: List[OptionDef]
):
    """
    Decorator to register a tool with metadata:
      - name: unique tool identifier
      - default_prompt: default system prompt for the tool
      - schema: list of option definitions for dynamic settings

    Also parses the function's docstring for summary/details and attaches them.
    """
    def decorator(fn):
        t: BaseTool = tool(name=name)(fn)
        # Attach metadata
        t.default_prompt = default_prompt
        t.settings_schema = schema
        # Parse docstring
        raw_doc = inspect.getdoc(fn) or ""
        lines = raw_doc.splitlines()
        t.description = lines[0] if lines else ''
        rest = lines[1:] if len(lines) > 1 else []
        if rest and not rest[0].strip():
            rest = rest[1:]
        t.long_description = '\n'.join(rest).strip()
        return t
    return decorator
