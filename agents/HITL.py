# agents/user_gateway.py
import logging
import asyncio

from framework import APIA_BaseAgent
from protocols import A2ATaskContext, A2ATaskResult, A2AClientManager
from models import A2AMessage, A2ATextPart, A2ADataPart, A2ATaskSendParams, A2AArtifact

logger = logging.getLogger(__name__)

class APIA_UserGatewayAgent(APIA_BaseAgent):
    """
    Handles interaction with end-users, translating natural language
    to/from A2A tasks for other agents.
    Example Skills: process_user_request, format_agent_response
    """

    async def handle_process_user_request_skill(self, context: A2ATaskContext) -> A2ATaskResult:
        logger.info(f"User Gateway ({self.id}) executing: process_user_request")
        user_query = " ".join(context.get_text_parts())
        if not user_query:
            return A2ATaskResult(status="failed", message=A2AMessage(role="agent", parts=[A2ATextPart(text="No user query provided.")]))

        await context.update_status("working", message_text="Understanding user request...")
        await asyncio.sleep(0.3) # Simulate NLU/Routing logic

        # --- Simple Routing Logic (Replace with actual NLU/LLM call) ---
        target_agent_url = None
        skill_id = None
        request_data = {"original_query": user_query}

        if "health" in user_query.lower() or "status" in user_query.lower():
            target_agent_url = "http://127.0.0.1:8000" # FIXME: Get AIOps URL dynamically
            skill_id = "monitor_health"
        elif "assess" in user_query.lower() and "tech" in user_query.lower():
             target_agent_url = "http://127.0.0.1:8000" # FIXME: Get CTO URL
             skill_id = "technology_assessment"
             # Extract tech name (very basic)
             parts = user_query.split()
             if len(parts) > parts.index("tech") + 1:
                 request_data["technology"] = parts[parts.index("tech") + 1]
        elif "process data" in user_query.lower():
             target_agent_url = "http://127.0.0.1:8000" # FIXME: Get DataProcessor URL
             skill_id = "process_data"
        # Add more routing rules...
        else:
            await context.update_status("working", message_text="Could not determine appropriate agent for the request.")
            return A2ATaskResult(status="failed", message=A2AMessage(role="agent", parts=[A2ATextPart(text="Sorry, I don't know how to handle that request.")]))
        # --- End Routing Logic ---

        await context.update_status("working", message_text=f"Routing request to handle '{skill_id}'...")

        # Forward task via A2A client
        a2a_message = A2AMessage(role="user", parts=[A2ATextPart(text=user_query)], metadata={"skill_id": skill_id, **request_data})
        params = A2ATaskSendParams(message=a2a_message)

        try:
            # Use self.a2a_client available from BaseAgent
            delegated_task = await self.a2a_client.send_task(target_agent_url, params)
            # Format the result back for the user (simplistic)
            final_response = f"Task {delegated_task.id} status: {delegated_task.status.state}.\n"
            if delegated_task.artifacts:
                 final_response += "Results:\n"
                 for art in delegated_task.artifacts:
                     for part in art.parts:
                         if isinstance(part, A2ATextPart): final_response += f"- {part.text}\n"
                         elif isinstance(part, A2ADataPart): final_response += f"- Data: {part.data}\n" # Basic display
            artifact = A2AArtifact(parts=[A2ATextPart(text=final_response)])
            return A2ATaskResult(status="completed", artifacts=[artifact])

        except Exception as e:
            logger.error(f"User Gateway failed to delegate task for skill {skill_id}: {e}", exc_info=True)
            return A2ATaskResult(status="failed", message=A2AMessage(role="agent", parts=[A2ATextPart(text=f"Sorry, there was an error processing your request: {e}")]))