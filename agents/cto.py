# agents/cto.py
import asyncio
import logging
import random

from framework import APIA_BaseAgent
from protocols import A2ATaskContext, A2ATaskResult
from models import A2AArtifact, A2ATextPart, A2ADataPart

logger = logging.getLogger(__name__)

class APIA_CTOAgent(APIA_BaseAgent):

    async def handle_technology_assessment_skill(self, context: A2ATaskContext) -> A2ATaskResult:
        logger.info(f"CTO ({self.id}) executing specific handler for: technology_assessment")
        await context.update_status("working", message_text="CTO assessing technology...")

        tech_to_assess = None
        if context.get_text_parts():
            tech_to_assess = context.get_text_parts()[0]
        elif context.metadata and context.metadata.get("technology"):
            tech_to_assess = context.metadata["technology"]

        if not tech_to_assess:
            return A2ATaskResult(status="failed", message=A2AMessage(role="agent", parts=[A2ATextPart(text="Missing technology name for assessment.")]))

        try:
            tech_stack = await self.knowledge_base.get_value("tech_stack", default={})
            approved = tech_stack.get("approved", [])
            experimental = tech_stack.get("experimental", [])
        except Exception as e:
            logger.error(f"CTO failed to access knowledge base: {e}")
            return A2ATaskResult(status="failed", message=A2AMessage(role="agent", parts=[A2ATextPart(text=f"Error accessing knowledge base: {e}")]))

        await asyncio.sleep(random.uniform(0.5, 1.5)) # Simulate assessment time

        assessment = {"technology": tech_to_assess, "scores": {}, "recommendation": "Undecided"}
        # Simplified assessment logic
        criteria = {
            "maturity": round(random.uniform(0.5, 1.0), 2),
            "support": round(random.uniform(0.6, 1.0), 2),
            "performance": round(random.uniform(0.7, 1.0), 2),
            "cost_efficiency": round(random.uniform(0.4, 0.9), 2),
            "alignment": round(random.uniform(0.5, 1.0), 2), # Strategic alignment
        }
        assessment["scores"] = criteria
        overall_score = sum(criteria.values()) / len(criteria)
        assessment["recommendation"] = "Recommended" if overall_score >= 0.7 else "Not Recommended"

        notes = []
        if tech_to_assess in approved: notes.append("Currently approved.")
        elif tech_to_assess in experimental: notes.append("Currently experimental.")
        else: notes.append("Not currently listed in tech stack.")
        assessment["notes"] = notes

        artifact = A2AArtifact(
            name=f"{tech_to_assess}_assessment",
            parts=[A2ADataPart(data=assessment)]
        )
        return A2ATaskResult(status="completed", artifacts=[artifact])

    # Add handlers for 'technical_design', 'system_architecture' if needed