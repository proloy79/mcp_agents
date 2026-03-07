from ..handlers import run_diagnostic_handler
from ..models import ToolMetadata, ToolDefinition

RUN_DIAGNOSTIC_DEF = ToolDefinition(
    metadata=ToolMetadata(
        name="run_diagnostic",
        description="Execute a diagnostic command on a target host."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "host": {
                "type": "string",
                "description": "Target host identifier",
                "pattern": "^[A-Za-z0-9_-]+$"
            },
            "check": {
                "type": "string",
                "enum": ["cpu_usage", "memory_usage", "disk_usage", "top_processes"],
                "description": "Diagnostic type to run"
            }
        },
        "required": ["check", "host"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "stdout": {"type": "string"},
            "stderr": {"type": "string"},
            "exit_code": {"type": "integer"},
        },
        "required": ["stdout", "stderr", "exit_code"],
    },
    handler=run_diagnostic_handler
)