# agents/ceo.py
import asyncio
import logging
from datetime import datetime

from framework import APIA_BaseAgent # Corrected import path assuming framework.py is in root
from protocols import A2ATaskContext, A2ATaskResult
from models import A2AArtifact, A2ATextPart, A2ADataPart

logger = logging.getLogger(__name__)

class APIA_CEOAgent(APIA_BaseAgent):

    # Specific handler for the 'strategic_planning' skill
    async def handle_strategic_planning_skill(self, context: A2ATaskContext) -> A2ATaskResult:
        logger.info(f"CEO ({self.id}) executing specific handler for: strategic_planning")
        await context.update_status("working", message_text="CEO reviewing strategic landscape...")

        # Access KB via self.knowledge_base (async)
        try:
            avg_health = await self.knowledge_base.get_metric("agent_health", "average_score", default=1.0)
            current_goals = await self.knowledge_base.get_value("strategic_goals", default={})
        except Exception as e:
            logger.error(f"CEO failed to access knowledge base: {e}")
            return A2ATaskResult(status="failed", message=A2AMessage(role="agent", parts=[A2ATextPart(text=f"Error accessing knowledge base: {e}")]))

        await asyncio.sleep(0.5) # Simulate thought process

        new_goals = current_goals.copy()
        update_summary = "No immediate changes to strategic goals based on current metrics."
        if avg_health < 0.75:
            new_target = new_goals.get("efficiency_target", 0.8) + 0.05
            new_goals["efficiency_target"] = round(new_target, 3) # Keep it tidy
            update_summary = f"Agent health ({avg_health:.2f}) below threshold. Increasing efficiency target to {new_goals['efficiency_target']}."
            logger.info(f"CEO: {update_summary}")

        new_goals["last_updated"] = datetime.now().isoformat()

        try:
            await self.knowledge_base.set_value("strategic_goals", new_goals)
        except Exception as e:
            logger.error(f"CEO failed to update knowledge base: {e}")
            return A2ATaskResult(status="failed", message=A2AMessage(role="agent", parts=[A2ATextPart(text=f"Error updating knowledge base: {e}")]))

        artifact = A2AArtifact(
            name="strategic_goal_update",
            parts=[
                A2ATextPart(text=update_summary),
                A2ADataPart(data=new_goals)
            ]
        )
        return A2ATaskResult(status="completed", artifacts=[artifact])

    # Specific handler for the 'oversight' skill
    async def handle_oversight_skill(self, context: A2ATaskContext) -> A2ATaskResult:
        logger.info(f"CEO ({self.id}) executing specific handler for: oversight")
        await context.update_status("working", message_text="CEO performing oversight review...")

        # Example: Get metric name from task metadata if provided
        metric_to_review = "average_health" # Default
        if context.metadata and context.metadata.get("metric"):
            metric_to_review = context.metadata["metric"]
        category = "agent_health" # Assuming category for now

        try:
            current_value = await self.knowledge_base.get_metric(category, metric_to_review)
            # history = await self.knowledge_base.get_metric_history(metric_name, category=category) # KB doesn't have history method
            goals = await self.knowledge_base.get_value("strategic_goals", default={})
            target = goals.get(f"{metric_to_review}_target")
        except Exception as e:
            logger.error(f"CEO oversight failed to access knowledge base: {e}")
            return A2ATaskResult(status="failed", message=A2AMessage(role="agent", parts=[A2ATextPart(text=f"Error accessing knowledge base: {e}")]))

        await asyncio.sleep(0.3) # Simulate analysis

        report = f"Oversight Report for '{category}.{metric_to_review}':\n"
        report += f"  - Current Value: {current_value if current_value is not None else 'N/A'}\n"
        report += f"  - Target: {target if target is not None else 'Not Set'}\n"
        status = "On Target / No Target"
        if target is not None and current_value is not None:
             if isinstance(current_value, (int, float)) and current_value < target:
                 status = "BELOW TARGET"
        report += f"  - Status: {status}"

        artifact = A2AArtifact(name="oversight_report", parts=[A2ATextPart(text=report)])
        return A2ATaskResult(status="completed", artifacts=[artifact])

    # Fallback handler (optional, depends if you want CEO to handle unexpected skills)
    # async def handle_a2a_task(self, context: A2ATaskContext) -> A2ATaskResult:
    #     return await super().handle_a2a_task(context)