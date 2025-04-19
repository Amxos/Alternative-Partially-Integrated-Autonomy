# agents/architect.py
import asyncio
import logging
from datetime import datetime

from framework import APIA_BaseAgent
from protocols import A2ATaskContext, A2ATaskResult
from models import A2AArtifact, A2ATextPart, A2ADataPart, A2AAgentSkill

logger = logging.getLogger(__name__)

class APIA_ArchitectAgent(APIA_BaseAgent):

    async def handle_evaluate_skill_coverage_skill(self, context: A2ATaskContext) -> A2ATaskResult:
        logger.info(f"Architect ({self.id}) executing specific handler for: evaluate_skill_coverage")
        await context.update_status("working", message_text="Architect evaluating skill coverage...")

        # Get observed tasks (needs to be provided in the request)
        observed_tasks = set(context.metadata.get("observed_tasks", [])) if context.metadata else set()
        if not observed_tasks:
             logger.warning("Evaluate skill coverage called with no observed tasks provided.")
             # Return empty or require input? Let's return empty for now.

        try:
            all_agents = await self.agent_registry.get_all_agents()
        except Exception as e:
            logger.error(f"Architect failed to get agents from registry: {e}")
            return A2ATaskResult(status="failed", message=A2AMessage(role="agent", parts=[A2ATextPart(text="Failed to retrieve agent list.")]))

        available_a2a_skills = set()
        # Concurrently get card info
        card_tasks = [agent.get_agent_card_info("http://placeholder") for agent in all_agents] # Need actual URLs or internal way
        results = await asyncio.gather(*card_tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, AgentCard):
                for skill in result.skills:
                    available_a2a_skills.add(skill.id)
            else:
                 logger.warning(f"Architect: Failed to get card info from an agent: {result}")


        unmet_skills = observed_tasks - available_a2a_skills
        logger.info(f"Architect: Skill coverage evaluated. Observed: {observed_tasks}, Available: {available_a2a_skills}, Unmet: {unmet_skills}")
        result_data = {"observed_skills": list(observed_tasks), "available_a2a_skills": list(available_a2a_skills), "unmet_skills": list(unmet_skills)}

        artifact = A2AArtifact(parts=[A2ADataPart(data=result_data)])
        return A2ATaskResult(status="completed", artifacts=[artifact])

    async def handle_propose_new_agent_skill(self, context: A2ATaskContext) -> A2ATaskResult:
        logger.info(f"Architect ({self.id}) executing specific handler for: propose_new_agent")
        await context.update_status("working", message_text="Architect designing new agent blueprint...")

        unmet_skill = context.metadata.get("unmet_skill") if context.metadata else None
        if not unmet_skill:
            return A2ATaskResult(status="failed", message=A2AMessage(role="agent", parts=[A2ATextPart(text="Missing 'unmet_skill' in request metadata.")]))

        # Define blueprint based on skill
        role_name = f"{unmet_skill.replace('_', ' ').title()} Specialist"
        # Default to GenericWorker, could be smarter
        class_name = "APIA_GenericWorkerAgent"
        new_skill = A2AAgentSkill(id=unmet_skill, name=role_name, description=f"Handles {unmet_skill} tasks via A2A.")

        blueprint = {
            "role": role_name,
            "class_name": class_name,
            "internal_skills": [],
            "a2a_skills": [new_skill.dict()], # Store as dict in KB
            "config": {"archetype": "standard"}, # Example override
            "status": "proposed",
            "proposed_at": datetime.now().isoformat()
        }

        try:
            agent_blueprints = await self.knowledge_base.get_value("agent_blueprints", default={})
            agent_blueprints[role_name] = blueprint # Add or overwrite
            await self.knowledge_base.set_value("agent_blueprints", agent_blueprints)
        except Exception as e:
            logger.error(f"Architect failed to update blueprints in KB: {e}")
            return A2ATaskResult(status="failed", message=A2AMessage(role="agent", parts=[A2ATextPart(text="Failed to save new blueprint.")]))

        logger.info(f"Architect: Proposed new agent blueprint for skill '{unmet_skill}'. Role: {role_name}")
        artifact = A2AArtifact(name="new_agent_blueprint", parts=[A2ADataPart(data={"blueprint_created": blueprint})])
        return A2ATaskResult(status="completed", artifacts=[artifact])