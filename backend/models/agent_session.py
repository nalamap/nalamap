from fastapi import Request, Depends
from typing import Dict, List
from models.settings_model import ToolConfig
from app.tools import tool_functions
from langchain_core.tools import BaseTool
from utility.tool_configurator import create_configured_tools


class AgentSession:
    def __init__(self):
        self.tool_settings: List[ToolConfig] = []
        self.configured_tools: Dict[str, BaseTool] = {}


async def get_agent_session(request: Request) -> AgentSession:
    if not hasattr(request.state, 'agent_session'):
        request.state.agent_session = AgentSession()
    return request.state.agent_session


async def get_configured_tools(
    session: AgentSession = Depends(get_agent_session)
):
    if not session.configured_tools:
        session.configured_tools = create_configured_tools(
            tool_functions, session.tool_settings, session
        )
    return session.configured_tools

