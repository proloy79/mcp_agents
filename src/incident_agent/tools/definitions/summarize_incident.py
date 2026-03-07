from ..handlers import summarize_incident_handler
from ..models import ToolMetadata, ToolDefinition

SUMMARIZE_INCIDENT_DEF = ToolDefinition(
    metadata=ToolMetadata(
        name="summarize_incident",
        description="Summarize an incident using alert ID and evidence."
    ),
    input_schema={
        "type": "object",
        "properties": {
            "alert_id": {"type": "string"},
            "evidence": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
        "required": ["alert_id"],
    },
    output_schema={
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "severity": {"type": "string"},
            "likely_cause": {"type": "string"},
        },
        "required": ["summary"],
    },
    handler=summarize_incident_handler
)