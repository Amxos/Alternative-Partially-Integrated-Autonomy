
# APIA (Alternative Partially Integrated Autonomy) 

## Overview

Alternative Partially Integrated Autonomy (APIA, related to the framework PIA) is an agent framework designed for building multi-agent systems with a focus on interoperability through standard protocols. It integrates concepts from the Model Context Protocol (MCP) for tool/resource access and the Agent2Agent (A2A) protocol for inter-agent communication and task management.

The framework is built using Python's `asyncio` for efficient I/O handling and `FastAPI` for exposing A2A endpoints. This version introduces modular code structure, external configuration, dependency injection, improved streaming, skill routing, and basic file handling placeholders.

## Core Features (v1.1)

*   **Asynchronous Foundation:** Built entirely on `asyncio`.
*   **Modular Structure:** Code split into logical modules (`main.py`, `config.py`, `models.py`, `framework.py`, `protocols.py`, `agents/`, etc.).
*   **External Configuration:** Loads settings (server ports, MCP connections, agent blueprints) from `config.yaml` via `pydantic-settings`.
*   **Dependency Injection:** Uses FastAPI's dependency injection for cleaner route handlers and better testability.
*   **A2A Protocol Server:**
    *   Implements core A2A methods (`tasks/send`, `tasks/get`, `tasks/cancel`).
    *   Improved Server-Sent Events (SSE) support for `tasks/sendSubscribe` with better error handling.
    *   Handles A2A task lifecycle (in-memory).
    *   Generates `/agent-card` and `/agents` listing endpoints.
    *   Skill-based routing for incoming A2A tasks to specific agent handlers.
*   **A2A Protocol Client:**
    *   Provides `A2AClientManager` (using `httpx`).
    *   Supports sending tasks (sync and streaming), getting status, canceling.
    *   Agent discovery via `/agent-card`.
*   **MCP Client Integration:**
    *   Provides `MCPClientManager`.
    *   Supports `stdio` connections (TCP placeholder).
    *   Allows agents to call MCP tools.
    *   **(Note: Requires actual `mcp` library; currently uses mocks).**
*   **File Handling (A2A):** Includes structure (`A2AFilePart`) and basic context helpers (`get_file_parts`, `process_file_part`) for handling files (base64 decoding implemented, URI fetching placeholder).
*   **Specialized Agents:** Refactored agent examples in `agents/` demonstrating A2A skill handlers.
*   **Monitoring & Status:** Basic `/health` endpoint; AIOps agent performs periodic checks; simplified Orchestrator logs metrics.

## Current State & Limitations

*   **MCP Integration Mocked:** Requires official `mcp` library integration and robust session management.
*   **A2A Persistence:** Task state is in-memory. Needs a persistent store (Redis, DB) for production.
*   **A2A Feature Gaps:** `tasks/resubscribe`, Push Notifications, Authentication are not implemented.
*   **File Handling:** Secure URI fetching for `A2AFilePart` needs implementation. Decisions on file storage/retrieval needed for agent-generated files.
*   **Testing:** Lacks a comprehensive test suite.
*   **Deployment:** No specific deployment scripts/configurations provided.
*   **Knowledge Base:** Internal async class; potential future MCP server.
*   **Internal Task Queue:** Still present in `APIA_BaseAgent`, potentially redundant.

## Project Structure

```
.
├── agents/             # Specialized agent implementations
│   ├── __init__.py
│   ├── ceo.py
│   ├── cto.py
│   ├── architect.py
│   ├── aiops.py
│   └── generic.py
├── config.py           # Pydantic models for config, YAML loading func
├── config.yaml         # Configuration file (create this from example)
├── dependencies.py     # FastAPI dependency provider functions
├── exceptions.py       # Custom exception classes
├── framework.py        # Core framework classes (BaseAgent, Registry, KB, Factory)
├── main.py             # FastAPI app definition, lifespan, routes, main runner
├── models.py           # Pydantic data models (A2A, MCP placeholders)
├── protocols.py        # MCP/A2A managers, router, context, results
├── requirements.txt    # Python dependencies (create this)
└── apia_refactored_system.log # Log file
```

## Setup Instructions

1.  **Prerequisites:** Python 3.8+, `pip`.
2.  **Clone:** `git clone <repository-url>` & `cd <repository-dir>`
3.  **Create `requirements.txt`:**
    ```txt
    fastapi[all]>=0.100.0,<0.111.0 # Use [all] for uvicorn, etc.
    httpx>=0.24.0,<0.28.0
    pydantic>=1.10.0,<3.0.0 # Check compatibility if using Pydantic v2 features
    pydantic-settings>=2.0.0,<3.0.0
    pyyaml>=6.0,<7.0
    sse-starlette-client>=1.6.0,<2.0.0 # Check correct package name if needed
    # Add 'mcp' when available
    ```
4.  **Install:** `pip install -r requirements.txt`
5.  **Configuration:** Create `config.yaml` (e.g., copy from example in docs/code) and customize paths, keys, ports.
6.  **Run:** `python main.py` (uses uvicorn internally based on config) or `uvicorn main:app --host <host> --port <port> --log-config=None`

## Next Steps / TODOs

*   Integrate the official `mcp` library.
*   Implement A2A task state persistence.
*   Add comprehensive unit and integration tests (`pytest`).
*   Implement remaining A2A features (resubscribe, push, auth).
*   Implement secure file handling (URI fetching, storage).
*   Refine A2A streaming behavior on errors/completion.
*   Externalize agent blueprints if they become large.
*   Evaluate phasing out the internal task queue.
*   Consider Knowledge Base as an MCP server.
*   Develop deployment strategies (Dockerfiles, etc.).

```

---
