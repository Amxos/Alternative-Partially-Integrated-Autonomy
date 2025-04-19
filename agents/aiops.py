# agents/aiops.py
import asyncio
import logging

from framework import APIA_BaseAgent, APIA_AgentFactory # Import Factory
from protocols import A2ATaskContext, A2ATaskResult
from models import A2AArtifact, A2ATextPart, A2ADataPart
from exceptions import AgentNotFoundError, ActionFailedError

logger = logging.getLogger(__name__)

class APIA_AIOpsEngineAgent(APIA_BaseAgent):
    # AIOps needs the factory to restart agents
    def __init__(self, agent_factory: APIA_AgentFactory, **kwargs):
        self.agent_factory = agent_factory
        # Ensure the parent class __init__ gets called correctly
        # Pass expected arguments to parent. We might need to adjust how Factory provides args.
        # Let's assume Factory passes all necessary args defined in BaseAgent init via kwargs
        super().__init__(**kwargs)
        logger.info(f"AIOps Engine ({self.id}) initialized with AgentFactory.")


    async def run_periodic(self):
         """Triggers periodic health monitor via A2A self-call."""
         logger.debug(f"AIOps ({self.id}) triggering periodic health monitor.")
         try:
              # Get own URL from settings (requires settings to be accessible)
              # This is a bit awkward, DI into agents might be better.
              # WORKAROUND: Assume KB stores the base URL or use a fixed local one.
              my_url = f"http://127.0.0.1:{8000}" # FIXME: Get actual host/port dynamically
              # Use self.a2a_client (available from BaseAgent)
              task_params = A2ATaskSendParams(
                  message={"role": "user", "parts": [], "metadata": {"skill_id": "monitor_health", "trigger": "periodic"}}
              )
              await self.a2a_client.send_task(my_url, task_params)
              # Follow up with recommend_actions maybe?
              # await asyncio.sleep(5) # Give monitoring time
              # recommend_params = A2ATaskSendParams(...) metadata={"skill_id": "recommend_actions"} ...
              # await self.a2a_client.send_task(my_url, recommend_params)
         except Exception as e:
              logger.error(f"AIOps failed to self-trigger monitoring via A2A: {e}", exc_info=True)


    async def handle_monitor_health_skill(self, context: A2ATaskContext) -> A2ATaskResult:
        logger.info(f"AIOps ({self.id}) executing: monitor_health")
        await context.update_status("working", message_text="AIOps gathering agent health data...")

        try:
            agents = await self.agent_registry.get_all_agents()
        except Exception as e:
             logger.error(f"AIOps monitor_health failed to get agents: {e}")
             return A2ATaskResult(status="failed", message=A2AMessage(role="agent", parts=[A2ATextPart(text="Failed to retrieve agent list.")]))

        health_scores = {}
        total_score = 0
        active_agents = 0

        # Get status and dependency concurrently
        agent_ids_to_monitor = [agent.id for agent in agents if agent.id != self.id]
        if not agent_ids_to_monitor:
            logger.info("AIOps monitor_health: No other agents found to monitor.")
            result_data = {"status": "Monitoring complete", "average_health": 1.0, "agent_health_scores": {}}
            artifact = A2AArtifact(parts=[A2ADataPart(data=result_data)])
            return A2ATaskResult(status="completed", artifacts=[artifact])

        status_tasks = {agent_id: asyncio.create_task(self.agent_registry.get_agent(agent_id).then(lambda a: a.get_status_summary() if a else None)) for agent_id in agent_ids_to_monitor}
        dep_status_tasks = {agent_id: asyncio.create_task(self.knowledge_base.get_agent_dependency_status(agent_id)) for agent_id in agent_ids_to_monitor}

        await asyncio.gather(*status_tasks.values(), *dep_status_tasks.values(), return_exceptions=True)

        for agent_id in agent_ids_to_monitor:
             try:
                status_result = await status_tasks[agent_id]
                dep_status = await dep_status_tasks[agent_id]

                if status_result is None:
                     logger.warning(f"AIOps: Agent {agent_id} not found during status check.")
                     continue # Skip agents that disappeared

                # Simplified health calculation
                status_score = 0.0 if status_result["status"] == "error" else 1.0
                total_processed = status_result["completed_task_count"] + status_result["error_count"]
                error_rate = status_result["error_count"] / total_processed if total_processed > 0 else 0
                error_score = 1.0 - min(error_rate, 1.0)
                dependency_score = 0.0 if dep_status else 1.0

                health = (status_score * 0.4 + error_score * 0.4 + dependency_score * 0.2)
                health = round(max(0.0, min(1.0, health)), 3)

                health_scores[agent_id] = health
                total_score += health
                active_agents += 1
             except Exception as e:
                 logger.error(f"AIOps: Failed to process health for agent {agent_id}: {e}")
                 health_scores[agent_id] = 0.0 # Mark as unhealthy if status check fails

        avg_score = round(total_score / active_agents, 3) if active_agents > 0 else 1.0
        try:
            await self.knowledge_base.update_metric("agent_health", "all_scores", health_scores)
            await self.knowledge_base.update_metric("agent_health", "average_score", avg_score)
        except Exception as e:
            logger.error(f"AIOps monitor_health failed to update KB: {e}")
            # Proceed without KB update if needed

        logger.info(f"AIOps: Health monitoring complete. Avg Health: {avg_score:.3f}")
        result_data = {"status": "Monitoring complete", "average_health": avg_score, "agent_health_scores": health_scores}
        artifact = A2AArtifact(parts=[A2ADataPart(data=result_data)])
        return A2ATaskResult(status="completed", artifacts=[artifact])


    async def handle_recommend_actions_skill(self, context: A2ATaskContext) -> A2ATaskResult:
        logger.info(f"AIOps ({self.id}) executing: recommend_actions")
        await context.update_status("working", message_text="AIOps analyzing health for recommendations...")

        try:
            health_scores = await self.knowledge_base.get_metric("agent_health", "all_scores", default={})
            aiops_config = await self.knowledge_base.get_value("aiops_config", default={"restart_threshold": 0.5})
            restart_threshold = aiops_config.get("restart_threshold", 0.5)
        except Exception as e:
             logger.error(f"AIOps recommend_actions failed to get data from KB: {e}")
             return A2ATaskResult(status="failed", message=A2AMessage(role="agent", parts=[A2ATextPart(text="Failed to retrieve health data.")]))

        recommendations = []
        agent_roles = {} # Cache roles to avoid multiple registry lookups
        agents_to_lookup = [agent_id for agent_id, score in health_scores.items() if score < restart_threshold]
        if agents_to_lookup:
            lookup_tasks = [self.agent_registry.get_agent(agent_id) for agent_id in agents_to_lookup]
            results = await asyncio.gather(*lookup_tasks, return_exceptions=True)
            for agent_id, result in zip(agents_to_lookup, results):
                 if isinstance(result, APIA_BaseAgent): agent_roles[agent_id] = result.role
                 else: logger.warning(f"AIOps recommend_actions: Agent {agent_id} not found during lookup.")


        for agent_id, score in health_scores.items():
            if score < restart_threshold and agent_id in agent_roles:
                recommendations.append({
                    "action": "restart_agent", "target_agent_id": agent_id,
                    "target_agent_role": agent_roles[agent_id], # Use cached role
                    "reason": f"Health score ({score:.2f}) below threshold ({restart_threshold})."
                    })

        logger.info(f"AIOps: Action recommendation complete. Found {len(recommendations)} recommendations.")
        artifact = A2AArtifact(parts=[A2ADataPart(data={"recommendations": recommendations})])
        return A2ATaskResult(status="completed", artifacts=[artifact])


    async def handle_execute_action_skill(self, context: A2ATaskContext) -> A2ATaskResult:
        logger.info(f"AIOps ({self.id}) executing: execute_action")

        action = context.metadata.get("action") if context.metadata else None
        target_id = context.metadata.get("target_agent_id") if context.metadata else None

        if not action or not target_id:
             return A2ATaskResult(status="failed", message=A2AMessage(role="agent", parts=[A2ATextPart(text="Missing 'action' or 'target_agent_id' in request metadata.")]))

        await context.update_status("working", message_text=f"AIOps attempting to execute '{action}' on agent {target_id}...")

        target_agent = await self.agent_registry.get_agent(target_id)
        if not target_agent:
            raise AgentNotFoundError(f"Target agent {target_id} not found for action {action}") # Let manager handle exception

        if action == "restart_agent":
            logger.info(f"AIOps executing restart for agent {target_agent.role} ({target_id})")
            target_role = target_agent.role

            try:
                await target_agent.stop() # Ensure graceful stop
                unregistered = await self.agent_registry.unregister(target_id)
                if not unregistered: logger.warning(f"AIOps: Agent {target_id} was already unregistered before restart.")

                # Use the injected factory to recreate
                new_agent = await self.agent_factory.create_agent(target_role, agent_id=target_id) # Reuse ID

                if new_agent:
                    new_agent.start() # Start the new agent's run loop
                    logger.info(f"Agent {target_role} restarted successfully. ID: {new_agent.id}")
                    result_data = {"status": "success", "message": f"Agent {target_role} restarted.", "new_agent_id": new_agent.id}
                    artifact = A2AArtifact(parts=[A2ADataPart(data=result_data)])
                    return A2ATaskResult(status="completed", artifacts=[artifact])
                else:
                    logger.error(f"Failed to recreate agent {target_role} using factory after stopping.")
                    # Should we try to register the old one back? Or leave it stopped?
                    raise ActionFailedError(f"Restart failed for {target_role} ({target_id}). Could not create replacement.")
            except Exception as e:
                 logger.error(f"Error during agent restart process for {target_id}: {e}", exc_info=True)
                 raise ActionFailedError(f"Restart process failed for {target_role} ({target_id}).") from e
        else:
            logger.warning(f"AIOps received unsupported action: {action}")
            raise NotImplementedError(f"AIOps cannot execute action: {action}")