# models.py
import uuid
import base64 # Added for FilePart handling
from datetime import datetime
from typing import Optional, Dict, List, Any, Union
from pydantic import BaseModel, Field, HttpUrl

# --- MCP Related (Placeholders/Examples) ---
class MCPToolInfo(BaseModel):
    name: str
    description: Optional[str] = None

class MCPResourceInfo(BaseModel):
    uri: str
    name: Optional[str] = None

# --- A2A Data Models (Based on Spec) ---
class A2APartMetadata(BaseModel):
    mimeType: Optional[str] = None
    schema_val: Optional[Dict[str, Any]] = Field(None, alias="schema") # Handle 'schema' keyword

    class Config:
        allow_population_by_field_name = True
        # Pydantic v2 config:
        # populate_by_name = True

class A2ATextPart(BaseModel):
    type: str = "text"
    text: str
    metadata: Optional[A2APartMetadata] = None

class A2AFile(BaseModel):
    name: Optional[str] = None
    mimeType: Optional[str] = None
    bytes: Optional[str] = None # base64 encoded
    uri: Optional[str] = None

class A2AFilePart(BaseModel):
    type: str = "file"
    file: A2AFile
    metadata: Optional[A2APartMetadata] = None

class A2ADataPart(BaseModel):
    type: str = "data"
    data: Dict[str, Any]
    metadata: Optional[A2APartMetadata] = None

A2APart = Union[A2ATextPart, A2AFilePart, A2ADataPart]

class A2AMessage(BaseModel):
    role: str # "user" or "agent"
    parts: List[A2APart]
    metadata: Optional[Dict[str, Any]] = None

class A2AArtifact(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parts: List[A2APart]
    metadata: Optional[Dict[str, Any]] = None
    index: int = 0
    append: Optional[bool] = False
    lastChunk: Optional[bool] = None

class A2ATaskState(BaseModel):
    state: str # "submitted", "working", "input-required", "completed", "canceled", "failed", "unknown"
    message: Optional[A2AMessage] = None
    timestamp: datetime = Field(default_factory=datetime.now) # Use default_factory

class A2ATask(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sessionId: Optional[str] = None
    status: A2ATaskState = Field(default_factory=lambda: A2ATaskState(state="submitted"))
    history: List[A2AMessage] = [] # Default to empty list
    artifacts: List[A2AArtifact] = [] # Default to empty list
    metadata: Optional[Dict[str, Any]] = None

class A2ATaskSendParams(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sessionId: Optional[str] = None
    message: A2AMessage
    acceptedOutputModes: List[str] = ["text/plain", "application/json"] # Default list
    historyLength: Optional[int] = 0
    # pushNotification: Optional[PushNotificationConfig] # Skipping
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        extra = 'allow' # Allow extra fields like skill_id temporarily if needed

class A2ATaskStatusUpdateEventResult(BaseModel):
    id: str
    status: A2ATaskState
    final: bool = False
    metadata: Optional[Dict[str, Any]] = None

class A2ATaskArtifactUpdateEventResult(BaseModel):
    id: str
    artifact: A2AArtifact
    metadata: Optional[Dict[str, Any]] = None

A2ATaskUpdateEventResult = Union[A2ATaskStatusUpdateEventResult, A2ATaskArtifactUpdateEventResult]

class A2AJsonRpcRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Union[str, int]
    method: str
    params: Optional[Dict[str, Any]] = None

class A2AJsonRpcSuccessResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Union[str, int]
    result: Any

class A2AJsonRpcErrorData(BaseModel):
    code: int
    message: str
    data: Optional[Any] = None

class A2AJsonRpcErrorResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Union[str, int, None]
    error: A2AJsonRpcErrorData

# Agent Card Models
class A2AAgentProvider(BaseModel):
    organization: str
    url: HttpUrl

class A2AAgentCapabilities(BaseModel):
    streaming: bool = False
    pushNotifications: bool = False
    stateTransitionHistory: bool = False

class A2AAgentAuthentication(BaseModel):
    schemes: List[str] = ["None"] # Default to None
    credentials: Optional[str] = None

class A2AAgentSkill(BaseModel):
    id: str
    name: str
    description: str
    tags: List[str] = []
    examples: List[str] = [] # Default to empty list
    inputModes: Optional[List[str]] = None
    outputModes: Optional[List[str]] = None

class AgentCard(BaseModel):
    name: str
    description: str
    url: HttpUrl
    provider: Optional[A2AAgentProvider] = None
    version: str = "0.1.0"
    documentationUrl: Optional[HttpUrl] = None
    capabilities: A2AAgentCapabilities = Field(default_factory=A2AAgentCapabilities)
    authentication: A2AAgentAuthentication = Field(default_factory=A2AAgentAuthentication)
    defaultInputModes: List[str] = ["text/plain", "application/json"]
    defaultOutputModes: List[str] = ["text/plain", "application/json"]
    skills: List[A2AAgentSkill] = []
