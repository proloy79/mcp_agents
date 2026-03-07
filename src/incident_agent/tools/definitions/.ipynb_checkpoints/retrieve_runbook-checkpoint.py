from ..handlers import retrieve_runbook_handler
from ..models import ToolMetadata, ToolDefinition

RETRIEVE_RUNBOOK_DEF = ToolDefinition(
    metadata=ToolMetadata(
        name="retrieve_runbook",
        description="Retrieve the most relevant runbook steps for a given query."
    ),
    input_schema={
        "type": "object",
        "title": "RetrieveRunbookInput",
        "description": "Query parameters for retrieving relevant runbook entries.",
        "properties": {
            "query": {
              "type": "string",
              "description": "Free-text query describing the issue or topic to search for."
            },
            "top_k": {
              "type": "integer",
              "description": "Maximum number of runbook entries to return.",
              "minimum": 1,
              "default": 5
            }
        },
        "required": ["query"]
    },      
    output_schema={
        "type": "object",
        "title": "RetrieveRunbookOutput",
        "description": "List of runbook entries matching the query.",
        "properties": {
            "results": {
                  "type": "array",
                  "description": "Top matching runbook entries.",
                  "items": {
                    "type": "object",
                    "properties": {
                      "title": {
                        "type": "string",
                        "description": "Short title describing the runbook scenario."
                      },
                      "steps": {
                        "type": "array",
                        "description": "Ordered list of diagnostic or remediation steps.",
                        "items": {
                          "type": "string"
                        }
                      },
                      "confidence": {
                        "type": "number",
                        "description": "Relevance score for this runbook entry.",
                        "minimum": 0.0,
                        "maximum": 1.0
                      }
                    },
                    "required": ["title", "steps", "confidence"]
                  }
            }
        },
        "required": ["results"]
    },
    handler=retrieve_runbook_handler
)