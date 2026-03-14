from dataclasses import dataclass, field
from typing import Any, Dict
import uuid
from .tracer import TraceRecorder
from incident_agent.tools import ToolSpecRegistry

@dataclass
class RunContext:
    trace_recorder: TraceRecorder   
    tool_spec_registry: ToolSpecRegistry
    audit_root: str = ""
    replay_mode: bool = False
    shared: Dict[str, Any] = field(default_factory=dict)
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))