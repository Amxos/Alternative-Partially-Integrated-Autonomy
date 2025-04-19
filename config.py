# config.py
import yaml
import logging
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field, HttpUrl, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from exceptions import ConfigurationError # Assuming exceptions.py exists

logger = logging.getLogger(__name__)

# --- Pydantic Models for Config Structure ---

class MCPServerConfig(BaseModel):
    name: str
    connection_type: str = "stdio" # 'stdio', 'tcp'
    command: Optional[str] = None
    args: Optional[List[str]] = None
    env: Optional[Dict[str, str]] = None
    host: Optional[str] = None
    port: Optional[int] = None

class A2AServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000
    # Add agent card defaults here if desired (name, description etc.)
    # name: "APIA Framework Server"

class Settings(BaseSettings):
    # Define fields corresponding to your config file structure
    log_level: str = "INFO"
    a2a_server: A2AServerConfig = Field(default_factory=A2AServerConfig)
    mcp_servers: List[MCPServerConfig] = []
    agent_blueprints: Dict[str, Dict] = {} # Load blueprints from config

    model_config = SettingsConfigDict(
        # Configure pydantic-settings if using .env files primarily
        # env_file = '.env'
        # extra = 'ignore'
    )

def load_config_from_yaml(path: str = "config.yaml") -> Settings:
    """Loads configuration from a YAML file and validates with Pydantic."""
    try:
        with open(path, 'r') as f:
            config_data = yaml.safe_load(f)
        if not config_data:
            raise FileNotFoundError("Config file is empty or invalid.")
        # Validate and create the Settings object
        settings = Settings(**config_data)
        return settings
    except FileNotFoundError:
        logger.error(f"Configuration file not found at: {path}")
        raise ConfigurationError(f"Config file {path} not found.")
    except yaml.YAMLError as e:
        logger.error(f"Error parsing configuration file {path}: {e}")
        raise ConfigurationError(f"Invalid YAML in {path}.")
    except ValidationError as e:
        logger.error(f"Configuration validation error: {e}")
        raise ConfigurationError(f"Invalid configuration structure: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred loading configuration: {e}", exc_info=True)
        raise ConfigurationError("Failed to load configuration.")

