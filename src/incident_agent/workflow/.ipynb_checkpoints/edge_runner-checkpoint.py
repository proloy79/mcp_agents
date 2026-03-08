from __future__ import annotations  # Future-proof typing.

import json  # Write a compact audit file.
import os  # Join paths.
import tempfile  # Ephemeral sandbox directory.
import time  # CPU guard.
from typing import Any, TypedDict, Protocol
import logging
from .observation import Observation
from .orchestrator import Orchestrator
import uuid
from dataclasses import dataclass, asdict 
from datetime import datetime, timezone


@dataclass
class TraceEvent:
    timestamp: str
    action: str            # observation/tool_call/tool_result/final_output/stop
    status: str
    payload: dict

class Writer(Protocol):
    def write(self, event: TraceEvent) -> None:
        ...
        
class TraceWriter():
    def __init__(self, path: str):
        self.path = path
        self.f = open(path, "w", encoding="utf-8")

    def write(self, event: TraceEvent):
        self.f.write(json.dumps(asdict(event)) + "\n")

    def close(self):
        self.f.close()

class InMemoryTraceWriter():
    def __init__(self, entries: List[str]):
        self.entries = entries
        self.entries = []

    def write(self, event: TraceEvent):
        self.entries.append(json.dumps(asdict(event)) + "\n")

    def close(self):
        pass

class TraceReader:
    def read_trace(self, path):
        events = []
        with open(path, "r") as f:
            for line in f:
                events.append(json.loads(line))
        return events 


class EdgeRunner:
    def __init__(self, mcp_client, audit_dir: str = "~/tmp/audit/incident_agent/", trace_writer: Writer | None = None,):
        self.orchestrator=Orchestrator(mcp_client)
        self.audit_dir = os.path.expanduser(audit_dir) 
        self.trace_writer = trace_writer
        self.logger = logging.getLogger(self.__class__.__name__)

    def _build_tasks_from_plan(self, plan_steps):
        tasks = {}
        #self.logger.debug(plan_steps)
        for i, step in enumerate(plan_steps, start=1):            
            # bind step at definition time
            def make_fn(step):
                return lambda ctx: self.client.call_tool(step.tool_name, step.input_schema)
    
            tasks[i] = Task(
                tool_name=step.tool_name,                
                fn=make_fn(step),
                deps=[], #@TODO: make the planner to setup dependencies properly
                skip_on_error=False,
            )
    
        return tasks    
    async def execute(self, observation: Observation): #  -- @TODO: , max_turns: int = 3,  cpu_ms: int = 50):
        self.logger.info(f"EdgeRunner called with prompt : {observation.text}\n")
        
        events: List[TraceEvents] = []  # Collect audit entries.
        cpu_start = time.process_time()  # Start CPU timer.

        # Log the user observation
        events.append(TraceEvent(
            timestamp = datetime.now(timezone.utc).isoformat(),
            action = "user_message",
            status = "ok",
            payload = {
                "text": observation.text
            }
        ))

        # @TODO: this needs to be implemented in the TaskGraph
        #for turn in range(1, max_turns + 1):  # Budgeted loop.
        #    # CPU guard: stop if over CPU budget.
        #    if int((time.process_time() - cpu_start) * 1000) > cpu_ms:                
        #        events.append(TraceEvent(
        #            timestamp = datetime.now(timezone.utc).isoformat(),
        #            turn = turn,
        #            action = "stop",
        #            status = "error",
        #            payload = {
        #                "errors": ["cpu budget breached"]
        #            }
        #        ))
        #        break  # Stop loop.
            
        plan, outputs = await self.orchestrator.handle_incident(observation)                

        if "errors" in plan and plan["errors"]:   
            events.append(TraceEvent(
                timestamp = datetime.now(timezone.utc).isoformat(),                
                action = "generate_plan",
                status = "error",
                payload = {
                    "errors": plan["errors"]                        
                }
            ))

        else:
            events.append(TraceEvent(
                timestamp = datetime.now(timezone.utc).isoformat(),
                action = "plan_generated",
                status = "ok",
                payload = {
                    "steps": [
                        {
                            "turn": turn,
                            "tool": step.tool_name,
                            "input": step.input_schema
                        }
                        for turn, step in enumerate(plan["steps"], start=1)
                    ]
                }
            ))

        audit_dir = os.path.expanduser(self.audit_dir)
        audit_dir = os.path.join(audit_dir, str(uuid.uuid4()))
        os.makedirs(audit_dir)
        audit_path = os.path.join(audit_dir, "audit.jsonl")
        trace = TraceWriter(audit_path)
        audit = os.path.join(audit_path, "audit.jsonl")  # Audit path.

        events.append(TraceEvent(
                timestamp = datetime.now(timezone.utc).isoformat(),                
                action = "tool_call_result",
                status = "ok",
                payload = {
                        "audit_path": audit,
                        "results": outputs                       
                    }
            ))
        
        trace_writer = self.trace_writer or TraceWriter(audit)
        for event in events:
            trace_writer.write(event)
        trace_writer.close()
    
        self._log_outputs(outputs)
    
        return {"output": outputs, "audit_path": audit}
            
    def _log_outputs(self, outputs: List[Dict[str, str]]) -> str:
        
        result_text = "\n".join(f"{item}" for item in outputs)
    
        self.logger.info(
            "\n"
            "---------------------------------------------------\n"            
            f"{result_text}\n"
            "---------------------------------------------------"
        )