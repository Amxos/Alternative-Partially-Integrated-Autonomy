# dependencies.py
from fastapi import Request, Depends

# Assuming components are stored in app.state during lifespan
from config import Settings
from framework import APIA_AgentRegistry, APIA_KnowledgeBase, APIA_AgentFactory
from protocols import A2ATaskManager, MCPClientManager, A2AClientManager

# These functions retrieve components initialized during startup

def get_settings(request: Request) -> Settings:
    if not hasattr(request.app.state, 'settings'):
         raise RuntimeError("Settings not initialized in app state")
    return request.app.state.settings

def get_agent_registry(request: Request) -> APIA_AgentRegistry:
    if not hasattr(request.app.state, 'agent_registry'):
         raise RuntimeError("AgentRegistry not initialized in app state")
    return request.app.state.agent_registry

def get_a2a_task_manager(request: Request) -> A2ATaskManager:
    if not hasattr(request.app.state, 'a2a_task_manager'):
         raise RuntimeError("A2ATaskManager not initialized in app state")
    return request.app.state.a2a_task_manager

def get_knowledge_base(request: Request) -> APIA_KnowledgeBase:
    if not hasattr(request.app.state, 'knowledge_base'):
        raise RuntimeError("KnowledgeBase not initialized in app state")
    return request.app.state.knowledge_base

def get_mcp_manager(request: Request) -> MCPClientManager:
    if not hasattr(request.app.state, 'mcp_manager'):
         raise RuntimeError("MCPClientManager not initialized in app state")
    return request.app.state.mcp_manager

def get_a2a_client(request: Request) -> A2AClientManager:
    if not hasattr(request.app.state, 'a2a_client'):
         raise RuntimeError("A2AClientManager not initialized in app state")
    return request.app.state.a2a_client

# Add get_agent_factory if needed by any routes
