from typing import List, Dict, Any, Optional, Callable
from pydantic import BaseModel
from dataclasses import dataclass  # Lightweight data containers.

class ToolMetadata(BaseModel):
    name: str
    description: str
    risk_level: str = "low"          # e.g. "low" | "medium" | "high"
    side_effects: str = "read-only"  # e.g. "read-only" | "executes-commands"

class ToolDefinition(BaseModel):
    metadata: ToolMetadata
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    handler: Callable[..., Any]

@dataclass  # Describe how a tool should be called.
class ToolExecutionSpec:
    name: str  # Logical tool name for logs.
    arguments: Dict[str, str]  # Expected payload keys → human type hints.
    timeout_ms: int = 200  # Max time per attempt in milliseconds.
    max_retries: int = 2  # Attempts after the first try.
    backoff_ms: int = 50  # Initial backoff between retries in ms.
    
