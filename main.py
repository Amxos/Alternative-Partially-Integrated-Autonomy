# main.py
import sys
import asyncio
import logging
import json # For SSE data serialization
from contextlib import asynccontextmanager

import fastapi # Use 'import fastapi' instead of 'from fastapi import FastAPI'
from fastapi import Depends, Response # Import Depends and Response
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.status import HTTP_200_OK, HTTP_503_SERVICE_UNAVAILABLE
from sse_starlette.sse import EventSourceResponse
import uvicorn

# Import from our modules
from config import Settings, load_config_from_yaml
from exceptions import ConfigurationError, A2AError
from models import (
    AgentCard, A2AJsonRpcRequest, A2AJsonRpcSuccessResponse,
    A2AJsonRpcErrorResponse, A2ATaskSendParams, A2ATaskUpdateEventResult,
    A2ATaskStatusUpdateEventResult, A2AJsonRpcErrorData
)
from framework import APIA_KnowledgeBase, APIA_AgentRegistry, APIA_AgentFactory
from protocols import (
    MCPClientManager, A2AClientManager, A2ATaskRouter, A2ATaskManager
)
from dependencies import (
    get_settings, get_agent_registry, get_a2a_task_manager, get_knowledge_base,
    get_mcp_manager, get_a2a_client
)
# Import agent types for factory discovery if needed here, but factory handles it now
# from agents import ceo, cto, architect, aiops, generic

logger = logging.getLogger(__name__)

# --- Orchestrator (Simplified) ---
class APIA_Orchestrator:
    # Keep simplified async orchestrator from previous step
    def __init__(self, knowledge_base: APIA_KnowledgeBase, agent_registry: APIA_AgentRegistry, a2a_client: A2AClientManager, app_settings: Settings):
        self.knowledge_base = knowledge_base
        self.agent_registry = agent_registry
        self.a2a_client = a2a_client
        self.settings = app_settings # Store settings if needed
        self._stop_event = asyncio.Event()
        self._run_task: Optional[asyncio.Task] = None
        logger.info("APIA Orchestrator initialized (Simplified).")

    async def submit_initial_tasks(self):
        logger.info("Orchestrator submitting initial tasks...")
        aiops_agents = [a for a in await self.agent_registry.get_all_agents() if a.role == "AIOpsEngine"]
        if aiops_agents:
            # Need agent factory to know which AIOps agent to target if multiple
            # Assuming one AIOps for now
             aiops_url = f"http://{self.settings.a2a_server.host}:{self.settings.a2a_server.port}"
             task_params = A2ATaskSendParams(
                 message={"role": "user", "parts": [], "metadata": {"skill_id": "monitor_health", "trigger": "startup"}}
             )
             try:
                 # Use await here
                 await self.a2a_client.send_task(aiops_url, task_params)
                 logger.info("Submitted initial monitor_health task to AIOps.")
             except Exception as e:
                 logger.error(f"Failed to submit initial monitor_health task: {e}")
        else:
             logger.warning("No AIOpsEngine found to submit initial monitoring task.")

    async def run(self):
        logger.info("APIA Orchestrator started run loop (Monitoring).")
        # Wait longer for agents and server to fully start before initial tasks
        await asyncio.sleep(10)
        await self.submit_initial_tasks()

        while not self._stop_event.is_set():
            try:
                await asyncio.sleep(60)
                logger.debug("Orchestrator performing periodic checks...")
                all_agents = await self.agent_registry.get_all_agents()
                avg_health = await self.knowledge_base.get_metric("agent_health", "average_score", "N/A")
                dlq_count = await self.knowledge_base.get_metric("a2a_tasks", "dlq_count", 0)
                logger.info(f"Orchestrator Monitor: Agents={len(all_agents)}, AvgHealth={avg_health}, A2A_DLQ={dlq_count}")

            except asyncio.CancelledError:
                logger.info("Orchestrator run loop cancelled.")
                break
            except Exception as e:
                logger.error(f"Orchestrator monitoring loop error: {e}", exc_info=True)
                await asyncio.sleep(30)

        logger.info("APIA Orchestrator stopped run loop.")

    def start(self):
        if not self._run_task or self._run_task.done():
             self._stop_event.clear()
             self._run_task = asyncio.create_task(self.run())
             logger.info("Orchestrator run task created.")

    async def stop(self):
        if self._stop_event.is_set(): return
        logger.info("Stopping Orchestrator...")
        self._stop_event.set()
        if self._run_task and not self._run_task.done():
            try: await asyncio.wait_for(self._run_task, timeout=5.0)
            except asyncio.TimeoutError: self._run_task.cancel()
            except Exception: pass # Ignore other errors on stop
        logger.info("Orchestrator stopped.")


# --- FastAPI Lifespan ---
@asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
    logger.info("APIA Application starting up...")
    # Load Config
    try:
        settings = load_config_from_yaml()
        app.state.settings = settings
        logging.getLogger().setLevel(settings.log_level)
        logger.info("Configuration loaded successfully.")
    except ConfigurationError:
        logger.critical("Failed to load configuration. Startup aborted.", exc_info=True)
        # A more robust way to signal startup failure might be needed
        raise RuntimeError("Configuration loading failed.") # Raise to stop FastAPI startup

    # Initialize Core Components & Store in app.state
    try:
        app.state.knowledge_base = APIA_KnowledgeBase()
        await app.state.knowledge_base.set_value("agent_blueprints", settings.agent_blueprints)

        app.state.agent_registry = APIA_AgentRegistry()
        app.state.mcp_manager = MCPClientManager(config=settings.mcp_servers)
        app.state.a2a_client = A2AClientManager()
        app.state.a2a_router = A2ATaskRouter()
        app.state.a2a_task_manager = A2ATaskManager(app.state.knowledge_base, app.state.a2a_router)
        app.state.agent_factory = APIA_AgentFactory(
            app.state.knowledge_base, app.state.agent_registry, app.state.mcp_manager,
            app.state.a2a_client, app.state.a2a_router
        )
        logger.info("Core components initialized.")
    except Exception as e:
         logger.critical(f"Failed to initialize core components: {e}", exc_info=True)
         raise RuntimeError("Core component initialization failed.") from e

    # Create Initial Agents
    initial_agent_roles = settings.agent_blueprints.keys()
    app.state.agent_tasks = []
    logger.info(f"Creating initial agents: {list(initial_agent_roles)}")
    for role in initial_agent_roles:
        try:
            agent = await app.state.agent_factory.create_agent(role)
            if agent:
                agent.start() # Starts the agent's async run loop
                if agent._run_task: app.state.agent_tasks.append(agent._run_task)
            else: logger.error(f"Failed to create initial agent: {role}")
        except Exception as e:
             logger.error(f"Error creating or starting agent '{role}': {e}", exc_info=True)
             # Decide whether to continue startup if an agent fails

    # Start Orchestrator
    try:
        app.state.orchestrator = APIA_Orchestrator(
            app.state.knowledge_base, app.state.agent_registry,
            app.state.a2a_client, settings
        )
        app.state.orchestrator.start()
        if app.state.orchestrator._run_task:
            app.state.agent_tasks.append(app.state.orchestrator._run_task)
        logger.info("Orchestrator started.")
    except Exception as e:
         logger.error(f"Failed to start orchestrator: {e}", exc_info=True)
         # Decide whether to proceed

    logger.info("APIA Application startup complete.")
    yield # Server runs here
    # --- Shutdown logic ---
    logger.info("APIA Application shutting down...")
    if hasattr(app.state, 'orchestrator'): await app.state.orchestrator.stop()
    # Stop agents first
    if hasattr(app.state, 'agent_registry'):
        agents_to_stop = await app.state.agent_registry.get_all_agents()
        if agents_to_stop:
            logger.info(f"Stopping {len(agents_to_stop)} agents...")
            stop_tasks = [agent.stop() for agent in agents_to_stop]
            results = await asyncio.gather(*stop_tasks, return_exceptions=True)
            for result, agent in zip(results, agents_to_stop):
                 if isinstance(result, Exception): logger.error(f"Error stopping agent {agent.id}: {result}")
    # Close managers
    if hasattr(app.state, 'mcp_manager'): await app.state.mcp_manager.close_all()
    if hasattr(app.state, 'a2a_client'): await app.state.a2a_client.close()
    # Optionally wait for agent run tasks to fully complete (already handled in agent.stop)
    # if hasattr(app.state, 'agent_tasks'):
    #     await asyncio.gather(*app.state.agent_tasks, return_exceptions=True)
    logger.info("APIA Application shutdown complete.")


# --- FastAPI App Definition ---
app = fastapi.FastAPI(title="APIA Agent Framework", version="1.1", lifespan=lifespan)

# --- API Routes ---
@app.get("/health", tags=["Status"])
async def health_check(registry: APIA_AgentRegistry = Depends(get_agent_registry)):
    """Basic health check: Checks if any agents are registered."""
    agents = await registry.get_all_agents()
    if agents:
         return Response(status_code=HTTP_200_OK, content="OK")
    else:
         # Return 503 if no agents are running, indicating service might be degraded
         return Response(status_code=HTTP_503_SERVICE_UNAVAILABLE, content="No agents registered or running.")

@app.get("/agent-card", response_model=AgentCard, tags=["A2A"])
async def get_agent_card(
    settings: Settings = Depends(get_settings),
    registry: APIA_AgentRegistry = Depends(get_agent_registry)
):
    """Provides the Agent Card for this APIA instance."""
    # For now, let's return a composite card or AIOps card.
    # Ideally, this endpoint might require an Agent ID or return a router card.
    aiops_agent = next((a for a in await registry.get_all_agents() if a.role == "AIOpsEngine"), None)
    base_url = f"http://{settings.a2a_server.host}:{settings.a2a_server.port}"
    if aiops_agent:
        return await aiops_agent.get_agent_card_info(base_url)
    else:
        # Fallback card representing the framework itself
        return AgentCard(
            name="APIA Framework Instance",
            description="Main entry point for the APIA Agent Framework",
            url=base_url,
            skills=[] # No direct skills, delegates internally
        )

@app.get("/agents", response_model=List[AgentCard], tags=["Status"])
async def list_registered_agents(
    registry: APIA_AgentRegistry = Depends(get_agent_registry),
    settings: Settings = Depends(get_settings)
):
    """Lists agent cards for all currently registered agents."""
    agents = await registry.get_all_agents()
    base_url = f"http://{settings.a2a_server.host}:{settings.a2a_server.port}"
    cards = []
    # Gather card info concurrently
    card_tasks = [agent.get_agent_card_info(base_url) for agent in agents]
    results = await asyncio.gather(*card_tasks, return_exceptions=True)
    for result, agent in zip(results, agents):
        if isinstance(result, AgentCard):
            cards.append(result)
        else:
            logger.error(f"Failed to get card for agent {agent.id}: {result}")
    return cards


@app.post("/", response_model=A2AJsonRpcSuccessResponse, responses={500: {"model": A2AJsonRpcErrorResponse}}, tags=["A2A"])
async def handle_a2a_request(
    request: A2AJsonRpcRequest,
    task_manager: A2ATaskManager = Depends(get_a2a_task_manager) # Inject Task Manager
):
    """Handles incoming A2A JSON-RPC requests (tasks/send, tasks/get, etc.)."""
    method = request.method
    params = request.params or {}
    request_id = request.id

    logger.info(f"Handling A2A request: Method={method}, ID={request_id}")

    try:
        if method == "tasks/send":
            task_params = A2ATaskSendParams(**params)
            result = await task_manager.handle_task_send(task_params)
            return A2AJsonRpcSuccessResponse(id=request_id, result=result)

        elif method == "tasks/sendSubscribe":
            task_params = A2ATaskSendParams(**params)
            # Use the improved event_generator from the previous step
            async def event_generator():
                 update_queue = asyncio.Queue()
                 async with task_manager._global_lock: # Access protected dict
                     task_manager._streaming_queues[task_params.id] = update_queue
                 # Start handler in background
                 handler_task = asyncio.create_task(task_manager.handle_task_send_subscribe(task_params, update_queue))
                 try:
                     while True:
                         queue_task = asyncio.create_task(update_queue.get())
                         done, pending = await asyncio.wait(
                             {handler_task, queue_task}, return_when=asyncio.FIRST_COMPLETED
                         )
                         if queue_task in done:
                             update = queue_task.result()
                             if isinstance(update, A2ATaskUpdateEventResult):
                                 yield {"event": "update", "data": json.dumps(A2AJsonRpcSuccessResponse(id=request_id, result=update).dict(exclude_none=True, by_alias=True))}
                                 if isinstance(update, A2ATaskStatusUpdateEventResult) and update.final: break
                             elif isinstance(update, A2AError): # Handle specific A2AErrors passed via queue
                                 yield {"event": "error", "data": json.dumps(A2AJsonRpcErrorResponse(id=request_id, error=update.to_rpc_error()).dict(exclude_none=True, by_alias=True))}
                                 break
                             elif isinstance(update, Exception): # Handle generic exceptions
                                 yield {"event": "error", "data": json.dumps(A2AJsonRpcErrorResponse(id=request_id, error=A2AJsonRpcErrorData(code=-32000, message=f"Stream error: {update}")).dict(exclude_none=True, by_alias=True))}
                                 break
                             elif update is None: break # Sentinel
                             update_queue.task_done()
                         elif handler_task in done:
                              try: handler_task.result() # Check for exceptions
                              except Exception as handler_exc:
                                   logger.error(f"SSE Handler task {task_params.id} failed directly: {handler_exc}", exc_info=True)
                                   yield {"event": "error", "data": json.dumps(A2AJsonRpcErrorResponse(id=request_id, error=A2AJsonRpcErrorData(code=-32000, message=f"Handler execution failed: {handler_exc}")).dict(exclude_none=True, by_alias=True))}
                              else: # Handler finished cleanly without final event?
                                  logger.warning(f"SSE Handler task {task_params.id} ended without final signal.")
                                  yield {"event": "error", "data": json.dumps(A2AJsonRpcErrorResponse(id=request_id, error=A2AJsonRpcErrorData(code=-32000, message="Handler task ended unexpectedly")).dict(exclude_none=True, by_alias=True))}
                              finally:
                                  if queue_task in pending: queue_task.cancel()
                                  break # Stop generation
                 except asyncio.CancelledError: logger.info(f"SSE event generator cancelled for task {task_params.id}")
                 finally:
                      async with task_manager._global_lock: # Cleanup queue
                         if task_params.id in task_manager._streaming_queues: del task_manager._streaming_queues[task_params.id]
                      if handler_task and not handler_task.done(): # Ensure handler task is cleaned up
                          handler_task.cancel()
                          try: await handler_task
                          except asyncio.CancelledError: pass
                          except Exception: pass # Logged already
            return EventSourceResponse(event_generator())

        elif method == "tasks/get":
            task_id = params.get("id")
            history = params.get("historyLength", 0)
            if not task_id: raise A2AError("Missing 'id' parameter for tasks/get", code=-32602)
            result = await task_manager.handle_task_get(task_id, history)
            return A2AJsonRpcSuccessResponse(id=request_id, result=result)

        elif method == "tasks/cancel":
            task_id = params.get("id")
            if not task_id: raise A2AError("Missing 'id' parameter for tasks/cancel", code=-32602)
            result = await task_manager.handle_task_cancel(task_id)
            return A2AJsonRpcSuccessResponse(id=request_id, result=result)

        else:
            logger.warning(f"Unsupported A2A method: {method}")
            raise A2AError(f"Method not found: {method}", code=-32601)

    except A2AError as e:
         logger.error(f"A2A Error (ReqID: {request_id}, Method: {method}): {e.message} (Code: {e.code})", exc_info=True)
         return JSONResponse(status_code=400, content=A2AJsonRpcErrorResponse(id=request_id, error=e.to_rpc_error()).dict(exclude_none=True, by_alias=True))
    except Exception as e:
        logger.exception(f"Internal Server Error (ReqID: {request_id}, Method: {method}): {e}")
        error_resp = A2AJsonRpcErrorResponse(id=request_id, error=A2AJsonRpcErrorData(code=-32603, message=f"Internal server error: {type(e).__name__}"))
        return JSONResponse(status_code=500, content=error_resp.dict(exclude_none=True, by_alias=True))


# --- Main Execution Block ---
if __name__ == "__main__":
    try:
        # Load config to get host/port before starting uvicorn
        startup_settings = load_config_from_yaml()
        server_host = startup_settings.a2a_server.host
        server_port = startup_settings.a2a_server.port
        print(f"Starting APIA Framework v1.1 on http://{server_host}:{server_port}")
        print("Check apia_refactored_system.log for detailed logs.")
        # Use log_config=None to prevent uvicorn from overriding our logging setup
        uvicorn.run("main:app", host=server_host, port=server_port, log_config=None)
    except ConfigurationError:
        print("FATAL: Could not load configuration. Server cannot start.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"FATAL: An unexpected error occurred during startup: {e}", file=sys.stderr)
        sys.exit(1)

