from __future__ import annotations  # Future-proof typing.

import json  # Write a compact audit file.
import os  # Join paths.
import tempfile  # Ephemeral sandbox directory.
import time  # CPU guard.
from typing import Any, TypedDict, Protocol
import logging
from .observation import Observation
from .orchestrator import Orchestrator
from dataclasses import dataclass, asdict 
from datetime import datetime, timezone
from .tracer import TraceEvent, TraceRecorder, TraceWriter
from .context import RunContext

class EdgeRunner:
    def __init__(self, mcp_client):
        self.orchestrator=Orchestrator(mcp_client)        
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
                deps=step.deps,
                skip_on_error=False,
            )
    
        return tasks   
        
    async def execute(self, observation: Observation, ctx: RunContext):
        self.logger.info(f"EdgeRunner called with replay mode: {ctx.replay_mode} prompt : {observation.text}\n")

        # Log the user observation
        ctx.trace_recorder.add(TraceEvent(
            run_id=ctx.run_id,
            timestamp = datetime.now(timezone.utc).isoformat(),
            action = "observation",            
            payload = {
                "text": observation.text
            }
        ))
            
        outputs = await self.orchestrator.handle_incident(observation, ctx)

        audit_dir = os.path.expanduser(ctx.audit_root)
        audit_dir = os.path.join(audit_dir, ctx.run_id)
        os.makedirs(audit_dir)
        audit = os.path.join(audit_dir, "audit.jsonl")  # Audit path.

        trace_writer = ctx.trace_recorder.trace_writer
        for event in ctx.trace_recorder.events:
            trace_writer.write(event)
        trace_writer.close()
                
        return {"output": outputs, "audit_path": audit}