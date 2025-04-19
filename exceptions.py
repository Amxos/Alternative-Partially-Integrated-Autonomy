# exceptions.py

class APIAException(Exception):
    """Base exception for APIA errors."""
    pass

class TaskExecutionError(APIAException):
    """Error during agent task execution."""
    pass

class AgentNotFoundError(APIAException):
    """Requested agent could not be found."""
    pass

class KnowledgeError(APIAException):
    """Error related to the Knowledge Base."""
    pass

class ActionFailedError(APIAException):
    """An agent action failed to complete."""
    pass

class ConfigurationError(APIAException):
    """Error related to loading or validating configuration."""
    pass

class A2AError(APIAException):
    """Error specific to A2A protocol interactions."""
    def __init__(self, message: str, code: int = -32000, data: any = None):
        super().__init__(message)
        self.message = message # Store message explicitly for easy access
        self.code = code
        self.data = data

    def to_rpc_error(self):
        """Formats the error for a JSON-RPC response."""
        from models import A2AJsonRpcErrorData # Avoid circular import at top level
        return A2AJsonRpcErrorData(code=self.code, message=self.message, data=self.data)
```
