# agents/generic.py
import asyncio
import logging
import random

from framework import APIA_BaseAgent
from protocols import A2ATaskContext, A2ATaskResult
from models import A2AArtifact, A2ATextPart, A2ADataPart, A2AFilePart

logger = logging.getLogger(__name__)

class APIA_GenericWorkerAgent(APIA_BaseAgent):

    # Example specific handler (assuming skill ID 'process_data')
    async def handle_process_data_skill(self, context: A2ATaskContext) -> A2ATaskResult:
        skill_id = "process_data" # Explicitly known here
        logger.info(f"Generic Worker {self.role} ({self.id}) executing specific handler for: {skill_id}")

        input_text = " ".join(context.get_text_parts())
        input_data = {}
        if context.metadata: input_data.update(context.metadata) # Get data from metadata? Or DataPart?

        file_parts = context.get_file_parts()
        processed_files_info = []

        msg = f"Processing {skill_id}..."
        if file_parts: msg += f" ({len(file_parts)} files)"
        await context.update_status("working", message_text=msg)

        # Process files (using placeholder logic)
        if file_parts:
            for file_part in file_parts:
                try:
                    file_content: bytes = await context.process_file_part(file_part)
                    logger.info(f"Generic Worker processed file '{file_part.file.name}', size: {len(file_content)} bytes")
                    processed_files_info.append({"name": file_part.file.name, "size": len(file_content), "status": "processed"})
                    await asyncio.sleep(0.1) # Simulate file processing time
                except Exception as e:
                    logger.error(f"Generic Worker failed to process file '{file_part.file.name}': {e}")
                    processed_files_info.append({"name": file_part.file.name, "status": "failed", "error": str(e)})

        # Simulate core work
        await asyncio.sleep(random.uniform(0.2, 0.8))

        if random.random() < 0.05: # 5% chance of failure
             logger.error(f"Generic worker {self.role} simulated failure for task {context.task_id}")
             return A2ATaskResult(status="failed", message=A2AMessage(role="agent", parts=[A2ATextPart(text="Simulated processing failure.")]))

        result_data = {
            "status": f"Successfully completed {skill_id}",
            "processed_text_length": len(input_text),
            "input_metadata_keys": list(input_data.keys()),
            "files_processed_summary": processed_files_info
        }
        artifact = A2AArtifact(parts=[A2ADataPart(data=result_data)])
        return A2ATaskResult(status="completed", artifacts=[artifact])

    # Keep the default handler as a fallback if this agent might receive other tasks
    # async def handle_a2a_task(self, context: A2ATaskContext) -> A2ATaskResult:
    #     return await super().handle_a2a_task(context)