# framework.py
import uuid
import asyncio
import logging
import importlib
import inspect
from datetime import datetime
from typing import Optional, Dict, List, Any, Set, Tuple, Union, Type, Callable

# Assuming other modules are in the same directory or accessible via PYTHONPATH
from models import AgentCard, A2AAgentSkill
from exceptions import ConfigurationError
# Explicitly import from protocols if needed, e.g., for type hinting managers
# from protocols import MCPClientManager, A2AClientManager, A2ATaskRouter

logger = logging.getLogger(__name__)

# Forward declaration for type hinting AgentFactory within BaseAgent if needed
# class APIA_AgentFactory: pass

class APIA_KnowledgeBase:
    # (Keep the async KB implementation from the previous step)
    def __init__(self):
        self._data: Dict[str, Any] = {
            "strategic_goals": {},
            "system_metrics": {"agent_health": {}, "a2a_tasks": {"received": 0, "completed": 0, "failed": 0}, "dlq_count": 0},
            "tech_stack": {"approved": ["python", "fastapi", "postgres", "react"], "experimental": ["rust", "chromadb"]},
            "architecture_blueprints": {},
            "agent_blueprints": {},
            "performance_history": {},
            "aiops_config": {"restart_threshold": 0.5, "monitoring_interval_sec": 60},
            "dependency_status": {}
        }
        self._lock = asyncio.Lock()
        logger.info("APIA Knowledge Base initialized (Async).")

    async def set_value(self, key: str, value: Any):
        async with self._lock:
            self._data[key] = value
            logger.debug(f"KnowledgeBase set: {key}")

    async def get_value(self, key: str, default: Any = None) -> Any:
        async with self._lock:
            return self._data.get(key, default)

    async def update_metric(self, metric_category: str, metric_name: str, value: Any):
        async with self._lock:
            metrics_data = self._data.setdefault("system_metrics", {})
            category_data = metrics_data.setdefault(metric_category, {})
            category_data[metric_name] = value

            if isinstance(value, (int, float)):
                history_key = f"{metric_category}.{metric_name}"
                history_data = self._data.setdefault("performance_history", {})
                history_list = history_data.setdefault(history_key, [])
                history_list.append((datetime.now(), value))
                self._data["performance_history"][history_key] = history_list[-100:]

            logger.debug(f"Metric updated: {metric_category}.{metric_name} = {value}")

    async def get_metric(self, metric_category: str, metric_name: str, default: Any = None) -> Any:
        async with self._lock:
            return self._data.get("system_metrics", {}).get(metric_category, {}).get(metric_name, default)

    async def get_agent_dependency_status(self, agent_id: str) -> bool:
        async with self._lock:
            return self._data.get("dependency_status", {}).get(agent_id, False)

    async def set_agent_dependency_status(self, agent_id: str, has_issues: bool):
        async with self._lock:
            self._data.setdefault("dependency_status", {})[agent_id] = has_issues
            logger.info(f"Dependency status for agent {agent_id} set to {has_issues}")


class APIA_AgentRegistry:
    # (Keep the async Registry implementation from the previous step)
    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            if cls._instance is None:
                cls._instance = super(APIA_AgentRegistry, cls).__new__(cls)
                cls._instance.agents: Dict[str, 'APIA_BaseAgent'] = {}
                cls._instance._agent_lock = asyncio.Lock()
        return cls._instance

    async def register(self, agent: 'APIA_BaseAgent'):
        async with self._agent_lock:
            if agent.id in self.agents:
                logger.warning(f"Agent {agent.id} ({agent.role}) already registered. Overwriting.")
            self.agents[agent.id] = agent
            logger.info(f"Agent registered: {agent.role} ({agent.id})")

    async def unregister(self, agent_id: str) -> bool:
        async with self._agent_lock:
            if agent_id not in self.agents:
                logger.warning(f"Attempt to unregister non-existent agent: {agent_id}")
                return False
            # Make sure agent is stopped before removing? AIOps does this now.
            del self.agents[agent_id]
            logger.info(f"Agent unregistered: {agent_id}")
            return True

    async def get_agent(self, agent_id: str) -> Optional['APIA_BaseAgent']:
        async with self._agent_lock:
            return self.agents.get(agent_id)

    async def get_all_agents(self) -> List['APIA_BaseAgent']:
        async with self._agent_lock:
            return list(self.agents.values())

    async def get_agents_by_skill(self, skill: str) -> List['APIA_BaseAgent']:
        """Finds agents by *internal* skills (A2A skills are advertised)."""
        async with self._agent_lock:
            return [agent for agent in self.agents.values() if skill in agent.internal_skills]


class APIA_BaseAgent:
    # (Keep the async Base Agent from the previous step, ensuring skill routing registration is included)
    # Make sure imports for dependencies like A2ATaskContext, A2ATaskResult, Managers are correct
    from protocols import MCPClientManager, A2AClientManager, A2ATaskRouter, A2ATaskContext, A2ATaskResult # noqa
    from models import A2AAgentSkill, AgentCard, A2AArtifact, A2ATextPart, A2ADataPart, A2AFilePart, A2AFile # noqa
    import base64 # For file handling

    def __init__(
        self,
        role: str,
        agent_id: str,
        knowledge_base: APIA_KnowledgeBase,
        agent_registry: APIA_AgentRegistry,
        mcp_manager: MCPClientManager,
        a2a_client: A2AClientManager,
        a2a_router: A2ATaskRouter,
        internal_skills: List[str],
        a2a_skills: List[A2AAgentSkill],
        config_override: Dict = {},
        initial_state: Dict = {}
    ):
        self.id = agent_id
        self.role = role
        self.knowledge_base = knowledge_base
        self.agent_registry = agent_registry
        self.mcp = mcp_manager
        self.a2a_client = a2a_client
        self.a2a_router = a2a_router
        self.internal_skills = set(internal_skills)
        self.a2a_skills = a2a_skills
        self.config = {"max_internal_queue_size": 100, **config_override} # Simple default config

        self.internal_task_queue = asyncio.PriorityQueue(maxsize=self.config["max_internal_queue_size"])
        """
        DEPRECATION WARNING (Potentially): This internal queue is primarily
        a remnant of the pre-A2A architecture or for self-scheduling internal
        periodic tasks (like AIOps monitoring trigger).

        Consider replacing its usage with A2A calls, potentially even self-calls
        (Agent makes an A2A call to its own endpoint), to standardize task processing.
        Keeping it for now allows handling purely internal logic loops or maintaining
        compatibility during transition. Evaluate removal in future iterations.
        """

        self.status = "initializing"
        self.current_internal_task_id = None
        self.error_count = 0
        self.completed_task_count = 0
        self.created_at = datetime.now()
        self._stop_event = asyncio.Event()
        self._lock = asyncio.Lock()
        self._run_task: Optional[asyncio.Task] = None

        # Register specific A2A skill handlers
        for skill in self.a2a_skills:
            handler_method_name = f"handle_{skill.id.replace('-', '_')}_skill" # Convention
            handler = getattr(self, handler_method_name, self.handle_a2a_task) # Fallback to default
            # Ensure the handler is actually awaitable
            if not asyncio.iscoroutinefunction(handler):
                 logger.error(f"A2A handler '{handler_method_name}' for skill '{skill.id}' in agent '{self.role}' is not an async function!")
                 # Optionally skip registration or raise error
                 continue
            # Registration needs to happen *after* the event loop is running, use create_task
            # If called before loop starts, this might cause issues. Better place might be agent.start()
            # Let's keep it here for now assuming it's called after loop starts.
            try:
                asyncio.create_task(self.a2a_router.register_handler(skill.id, handler))
            except RuntimeError as e:
                 logger.warning(f"Could not register handler for {skill.id} during init (event loop might not be running?): {e}")


        # Register with registry (needs event loop running too)
        try:
             asyncio.create_task(self.agent_registry.register(self))
        except RuntimeError as e:
             logger.warning(f"Could not register agent {self.role} during init (event loop might not be running?): {e}")

        self.status = "idle"


    async def initialize_state(self, state: Dict):
        logger.info(f"Agent {self.role} ({self.id}) initializing state.")
        # Add specific state loading logic here if needed
        await asyncio.sleep(0.01)

    async def receive_internal_task(self, task: Dict):
        async with self._lock:
            try:
                await self.internal_task_queue.put((-task.get("priority", 5), task))
                logger.info(f"Agent {self.role} ({self.id}) received internal task")
            except asyncio.QueueFull:
                 logger.warning(f"Agent {self.role} ({self.id}) internal queue full. Discarding task.")


    async def run(self):
        logger.info(f"Agent {self.role} ({self.id}) started run loop.")
        self.status = "idle"
        # Register handlers here maybe, if loop is guaranteed running?
        # for skill in self.a2a_skills: ... register ...
        # await self.agent_registry.register(self) # Ensure registration happens within running loop

        while not self._stop_event.is_set():
            try:
                neg_priority, task_data = await asyncio.wait_for(
                    self.internal_task_queue.get(), timeout=30.0
                )

                async with self._lock:
                    self.status = "busy"
                    self.current_internal_task_id = task_data.get("id", "N/A")

                try:
                    logger.info(f"Agent {self.role} ({self.id}) starting internal task: {task_data.get('type', 'N/A')}")
                    result = await self.execute_internal_task(task_data)
                    self.completed_task_count += 1
                    logger.debug(f"Internal task {self.current_internal_task_id} completed with result: {result}")
                except Exception as e:
                    logger.error(f"Agent {self.role} ({self.id}) failed executing internal task {self.current_internal_task_id}: {e}", exc_info=True)
                    self.error_count += 1
                finally:
                    async with self._lock:
                        self.status = "idle"
                        self.current_internal_task_id = None
                    self.internal_task_queue.task_done()

            except asyncio.TimeoutError:
                await self.run_periodic()
            except asyncio.CancelledError:
                 logger.info(f"Agent {self.role} ({self.id}) run loop cancelled.")
                 break
            except Exception as e:
                logger.error(f"Agent {self.role} ({self.id}) encountered error in run loop: {e}", exc_info=True)
                async with self._lock:
                    self.status = "error"
                await asyncio.sleep(5)

        logger.info(f"Agent {self.role} ({self.id}) stopped run loop.")
        self.status = "stopped"

    async def run_periodic(self):
        pass # Subclasses override

    async def execute_internal_task(self, task_data: Dict) -> Any:
        logger.warning(f"{self.role} agent received internal task but execute_internal_task is not implemented: {task_data.get('type')}")
        await asyncio.sleep(0.1)
        return {"status": "ignored"}

    # Default A2A Handler (integrates file part logic)
    async def handle_a2a_task(self, context: 'A2ATaskContext') -> 'A2ATaskResult':
        skill_id_attempt = context.task.metadata.get("skill_id", "unknown") if context.task.metadata else "unknown"
        logger.warning(f"{self.role} ({self.id}) received A2A task using default handler for skill '{skill_id_attempt}'.")

        incoming_text = context.get_text_parts()
        file_parts = context.get_file_parts()
        processed_files_info = []

        await context.update_status("working", message_text="Processing your request...")

        if file_parts:
             await context.update_status("working", message_text=f"Processing {len(file_parts)} files...")
             for file_part in file_parts:
                  try:
                      file_content = await context.process_file_part(file_part) # Use the context method
                      processed_files_info.append({"name": file_part.file.name, "size": len(file_content), "status": "processed (placeholder)"})
                  except Exception as e:
                      logger.error(f"Failed to process file '{file_part.file.name}' in default handler: {e}")
                      processed_files_info.append({"name": file_part.file.name, "status": "failed", "error": str(e)})

        await asyncio.sleep(0.5)

        response_text = f"Echo from {self.role} ({skill_id_attempt}): Received task {context.task_id}. "
        response_text += f"Text: '{' '.join(incoming_text)}'. " if incoming_text else "No text input. "
        response_text += f"Files: {len(processed_files_info)} processed."

        artifact = A2AArtifact(
             parts=[
                 A2ATextPart(text=response_text),
                 A2ADataPart(data={"files_processed": processed_files_info})
             ]
        )
        return A2ATaskResult(status="completed", artifacts=[artifact])


    async def get_agent_card_info(self, base_url: str) -> AgentCard:
        async with self._lock:
            # Ensure URL is valid
            try:
                validated_url = HttpUrl(url=f"{base_url.rstrip('/')}")
            except Exception:
                 logger.error(f"Invalid base_url provided for agent card: {base_url}")
                 validated_url = HttpUrl(url="http://invalid.url") # Fallback

            return AgentCard(
                name=self.role,
                description=f"APIA Agent performing role: {self.role}",
                url=validated_url,
                version="1.1-modular",
                capabilities=A2AAgentCapabilities(streaming=True), # Assume streaming
                skills=self.a2a_skills,
            )

    async def get_status_summary(self) -> Dict:
        async with self._lock:
            q_size = self.internal_task_queue.qsize() if self.internal_task_queue else 0
            return {
                "id": self.id, "role": self.role, "status": self.status,
                "internal_queue_size": q_size,
                "current_internal_task_id": self.current_internal_task_id,
                "error_count": self.error_count,
                "completed_task_count": self.completed_task_count,
                "created_at": self.created_at.isoformat(),
            }

    def start(self):
        if not self._run_task or self._run_task.done():
            self._stop_event.clear()
            # Ensure registration happens after loop starts if init fails
            async def _start_and_register():
                 # Maybe register here instead of __init__?
                 # await self.agent_registry.register(self)
                 # for skill in self.a2a_skills: ... await self.a2a_router.register_handler(...) ...
                 await self.run()
            self._run_task = asyncio.create_task(_start_and_register())
            logger.info(f"Agent {self.role} ({self.id}) run task created.")
        else:
            logger.warning(f"Agent {self.role} ({self.id}) start called but task is already running.")

    async def stop(self):
         # (Keep the async stop implementation from the previous step)
        if self._stop_event.is_set(): return
        logger.info(f"Stopping agent {self.role} ({self.id})...")
        self._stop_event.set()
        # Signal internal queue to unblock getter if waiting
        try: await self.internal_task_queue.put((float('inf'), None)) # Sentinel
        except asyncio.QueueFull: pass

        if self._run_task and not self._run_task.done():
             try:
                 # Wait briefly, then cancel if needed
                 await asyncio.wait_for(self._run_task, timeout=5.0)
             except asyncio.TimeoutError:
                 logger.warning(f"Agent {self.role} ({self.id}) run loop did not stop gracefully, cancelling.")
                 self._run_task.cancel()
                 try: await self._run_task
                 except asyncio.CancelledError: pass
             except Exception as e: logger.error(f"Error waiting for agent {self.role} stop: {e}")
        logger.info(f"Agent {self.role} ({self.id}) stopped signal processed.")
        self.status = "stopped"


class APIA_AgentFactory:
    # (Keep the async Factory implementation, ensure it imports agent classes correctly)
    _agent_classes: Dict[str, Type['APIA_BaseAgent']] = {}

    def __init__(self, knowledge_base: APIA_KnowledgeBase, agent_registry: APIA_AgentRegistry, mcp_manager: 'MCPClientManager', a2a_client: 'A2AClientManager', a2a_router: 'A2ATaskRouter'):
        self.knowledge_base = knowledge_base
        self.agent_registry = agent_registry
        self.mcp_manager = mcp_manager
        self.a2a_client = a2a_client
        self.a2a_router = a2a_router
        # Discover classes only once
        if not APIA_AgentFactory._agent_classes:
             APIA_AgentFactory._agent_classes = self._discover_agent_classes()
             logger.info(f"Agent Factory discovered agent classes: {list(APIA_AgentFactory._agent_classes.keys())}")

    def _discover_agent_classes(self) -> Dict[str, type]:
        # Need to import agent modules explicitly now
        from agents import ceo, cto, architect, aiops, generic # Assuming these files exist in 'agents' package
        classes = {}
        # List known types manually is often more robust than reflection across modules
        known_types = [
            ceo.APIA_CEOAgent, cto.APIA_CTOAgent, architect.APIA_ArchitectAgent,
            aiops.APIA_AIOpsEngineAgent, generic.APIA_GenericWorkerAgent
        ]
        for cls in known_types:
             if issubclass(cls, APIA_BaseAgent) and cls != APIA_BaseAgent:
                 classes[cls.__name__] = cls
        return classes

    async def create_agent(self, blueprint_role: str, agent_id: Optional[str] = None) -> Optional['APIA_BaseAgent']:
        logger.info(f"Agent Factory creating agent for role: {blueprint_role}")
        blueprints = await self.knowledge_base.get_value("agent_blueprints", {})
        blueprint = blueprints.get(blueprint_role)

        if not blueprint:
            logger.error(f"Blueprint not found for role: {blueprint_role}")
            return None

        class_name = blueprint.get("class_name")
        agent_class = APIA_AgentFactory._agent_classes.get(class_name) if class_name else None
        if not agent_class:
            logger.error(f"Agent class '{class_name or 'N/A'}' not found or missing in blueprint for role: {blueprint_role}")
            return None

        # Get details from blueprint, providing defaults
        internal_skills = blueprint.get("internal_skills", [])
        # Ensure a2a_skills are parsed into models if stored as dicts in YAML
        a2a_skill_dicts = blueprint.get("a2a_skills", [])
        a2a_skills = [A2AAgentSkill(**s) for s in a2a_skill_dicts if isinstance(s, dict)]
        agent_config_override = blueprint.get("config", {})
        has_dependency_issues = blueprint.get("has_dependency_issues", False)
        initial_state = blueprint.get("initial_state", {})

        try:
            # Pass all required dependencies to the agent constructor
            constructor_kwargs = {
                "role": blueprint_role,
                "agent_id": agent_id or str(uuid.uuid4()),
                "knowledge_base": self.knowledge_base,
                "agent_registry": self.agent_registry,
                "mcp_manager": self.mcp_manager,
                "a2a_client": self.a2a_client,
                "a2a_router": self.a2a_router,
                "internal_skills": internal_skills,
                "a2a_skills": a2a_skills,
                "config_override": agent_config_override,
                "initial_state": initial_state
            }
            # Handle agents like AIOps that need the factory itself
            if agent_class == aiops.APIA_AIOpsEngineAgent: # Need to import aiops module
                 constructor_kwargs["agent_factory"] = self # Pass self

            new_agent = agent_class(**constructor_kwargs)

            await self.knowledge_base.set_agent_dependency_status(new_agent.id, has_dependency_issues)
            # Initialization called within agent.start() or separately? Let's keep it separate for now.
            await new_agent.initialize_state(initial_state)

            logger.info(f"Successfully created agent {new_agent.role} ({new_agent.id}).")
            return new_agent
        except Exception as e:
            logger.error(f"Failed to instantiate agent class {class_name} for role {blueprint_role}: {e}", exc_info=True)
            return None

