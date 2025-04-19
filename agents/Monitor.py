# agents/resource_monitor.py
import logging
import asyncio

from framework import APIA_BaseAgent
from protocols import A2ATaskContext, A2ATaskResult, MCPClientManager
from models import A2AArtifact, A2ATextPart, A2ADataPart

logger = logging.getLogger(__name__)

class APIA_ResourceMonitorAgent(APIA_BaseAgent):
    """
    Monitors external resource usage via MCP or direct checks.
    Example Skills: check_api_quota, check_db_connections
    """

    # Example specific handler
    async def handle_check_api_quota_skill(self, context: A2ATaskContext) -> A2ATaskResult:
        logger.info(f"Resource Monitor ({self.id}) executing: check_api_quota")
        target_api = context.metadata.get("target_api") if context.metadata else "unknown_api"
        mcp_server_name = context.metadata.get("mcp_server") if context.metadata else None # e.g., "google_cloud_monitor_mcp"

        await context.update_status("working", message_text=f"Checking quota for API: {target_api}...")

        quota_info = {"api": target_api, "limit": None, "usage": None, "status": "unknown"}
        if mcp_server_name:
            try:
                # Assume an MCP tool exists on the specified server
                mcp_result = await self.mcp.call_tool(mcp_server_name, "get_api_quota", {"api_name": target_api})
                # Parse mcp_result (structure depends on the MCP tool)
                quota_info.update(mcp_result if isinstance(mcp_result, dict) else {"raw_result": mcp_result})
                quota_info["status"] = "checked_via_mcp"
                await asyncio.sleep(0.2) # Simulate MCP call time
            except Exception as e:
                logger.error(f"Resource Monitor failed to check quota for {target_api} via MCP {mcp_server_name}: {e}")
                quota_info["status"] = f"mcp_error: {e}"
        else:
            logger.warning(f"Resource Monitor: No MCP server specified for API quota check: {target_api}")
            quota_info["status"] = "no_mcp_server"
            await asyncio.sleep(0.1) # Simulate local failure

        artifact = A2AArtifact(parts=[A2ADataPart(data=quota_info)])
        return A2ATaskResult(status="completed", artifacts=[artifact])

    # Add other resource checking handlers (e.g., db connections)