# agents/compliance.py
import logging
import asyncio

from framework import APIA_BaseAgent
from protocols import A2ATaskContext, A2ATaskResult
from models import A2AMessage, A2ATextPart, A2ADataPart, A2AArtifact

logger = logging.getLogger(__name__)

class APIA_ComplianceAgent(APIA_BaseAgent):
    """
    Monitors specific tasks or KB changes for compliance violations.
    Example Skills: audit_task_completion, check_kb_change
    """
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Load compliance rules (e.g., from config or KB)
        self.rules = {
            "PII_IN_ARTIFACTS": {"enabled": True, "keywords": ["ssn", "credit card", "password"]},
            "UNAPPROVED_TECH_PROPOSED": {"enabled": True}
        }
        logger.info(f"Compliance Agent ({self.id}) initialized with rules: {list(self.rules.keys())}")


    # This agent might not handle direct A2A requests, but subscribe to events
    # or be triggered by other agents/orchestrator.
    # Let's make a skill to be called *after* another task completes.
    async def handle_audit_task_completion_skill(self, context: A2ATaskContext) -> A2ATaskResult:
        logger.info(f"Compliance Agent ({self.id}) executing: audit_task_completion")

        # Get details of the completed task (passed in metadata)
        original_task_id = context.metadata.get("original_task_id") if context.metadata else None
        original_task_artifacts = context.metadata.get("original_task_artifacts") if context.metadata else [] # Simplified - need real artifact data

        if not original_task_id:
             return A2ATaskResult(status="failed", message=A2AMessage(role="agent", parts=[A2ATextPart(text="Missing original_task_id for audit.")]))

        await context.update_status("working", message_text=f"Auditing artifacts for task {original_task_id}...")
        await asyncio.sleep(0.2) # Simulate check

        violations = []
        # Rule: Check for PII keywords in text artifacts
        if self.rules["PII_IN_ARTIFACTS"]["enabled"]:
            keywords = self.rules["PII_IN_ARTIFACTS"]["keywords"]
            for artifact_dict in original_task_artifacts: # Assuming artifacts are passed as dicts
                 try:
                    artifact = A2AArtifact(**artifact_dict) # Parse back to model
                    for part in artifact.parts:
                         if isinstance(part, A2ATextPart):
                             for keyword in keywords:
                                 if keyword in part.text.lower():
                                     violations.append(f"Potential PII ('{keyword}') detected in artifact '{artifact.name or artifact.index}' of task {original_task_id}")
                                     # Break inner loop once keyword found in part
                                     break
                 except Exception as e:
                      logger.warning(f"Compliance: Error parsing artifact for audit: {e}")


        # Add more rule checks here...

        if violations:
            logger.warning(f"Compliance violations found for task {original_task_id}: {violations}")
            # Optionally: Trigger alert, quarantine result, require human review (e.g., call gotoHuman MCP)
            result_text = f"Compliance Violations Found for task {original_task_id}:\n" + "\n".join(f"- {v}" for v in violations)
            status = "completed_with_violations" # Custom status? Or use metadata?
        else:
            logger.info(f"Compliance check passed for task {original_task_id}.")
            result_text = f"Compliance check passed for task {original_task_id}."
            status = "completed"

        artifact = A2AArtifact(parts=[A2ATextPart(text=result_text), A2ADataPart(data={"violations": violations})])
        # Use custom status in result message, final task status is 'completed'
        message = A2AMessage(role="agent", parts=[A2ATextPart(text=result_text)], metadata={"compliance_status": status})
        return A2ATaskResult(status="completed", message=message, artifacts=[artifact])