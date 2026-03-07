from __future__ import annotations

from dataclasses import dataclass  # Lightweight records.
from typing import Dict, List  # Type hints for clarity.
import logging

@dataclass
class PlanStep:
    """One actionable step produced by the planner."""

    tool_name: str  # Name of the tool to invoke (e.g., "calculator").
    call_type: str
    input_schema: Dict[str, str]  # Key → hint (e.g., {"expression": "str"}).
    notes: str  # Short human note (≤ 12 words).
    
class LLMPlanner:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        #short term memory to store every tool call result for this particular incident to avoid repeating same steps
        # self.episodic = [] 

    def plan(self, incident_text: str, memory_snippet: str) -> Dict[str, Any]:
        """
        Get the plan from LLM, validate and return
        """        
        plan = self._fake_llm_plan(incident_text, memory_snippet)            
        problems=self._validate_plan(plan["steps"])
        
        if problems:            
            return {
                "steps": [],
                "errors": problems
            } 
        #self.logger.info(f"in planner  ---------- {render_plan(plan["steps"])}")
        return plan

    def _fake_llm_plan(self, prompt: str, memory_snippet: str) -> List[PlanStep]:
        """
        Fake LLM planner that branches into CPU spike, service restart loop,
        or service unavailable scenarios based on the prompt text.
        """
    
        prompt_l = prompt.lower()
    
        # get the host
        if "host a" in prompt_l:
            host = "A"
        elif "host b" in prompt_l:
            host = "B"
        else:
            host = "UNKNOWN"
    
        # identify the context
        if "cpu spike" in prompt_l or "high cpu" in prompt_l:
            scenario = "cpu"
        elif "restart loop" in prompt_l or "crash" in prompt_l or "looping" in prompt_l:
            scenario = "restart_loop"
        elif "service unavailable" in prompt_l or "unavailable" in prompt_l:
            scenario = "unavailable"
        else:
            scenario = "unknown"
    
        # is this a repeated instace
        repeated = f"host {host.lower()}" in memory_snippet.lower()
    
        steps = []
    
        # cpu spike
        if scenario == "cpu":
            # Step 1: CPU diagnostic
            steps.append(
                PlanStep(
                    tool_name="run_diagnostic",
                    call_type="tool_call",
                    input_schema={"host": host, "check": "cpu_usage"},
                    notes=f"Check CPU usage on host {host}",
                )
            )
    
            # Step 2: Repeated or first-time logic
            if repeated:
                steps.append(
                    PlanStep(
                        tool_name="run_diagnostic",
                        call_type="tool_call",
                        input_schema={"host": host, "check": "compare_previous"},
                        notes=f"Compare CPU metrics with previous incidents on host {host}",
                    )
                )
            else:
                steps.append(
                    PlanStep(
                        tool_name="run_diagnostic",
                        call_type="tool_call",
                        input_schema={"host": host, "check": "top_processes"},
                        notes=f"Identify top CPU-consuming processes on host {host}",
                    )
                )
        
            # Step 3: CPU runbook
            steps.append(
                PlanStep(
                    tool_name="retrieve_runbook",
                    call_type="tool_call",
                    input_schema={"query": "cpu spike", "top_k": 3},
                    notes="Fetch runbook steps for CPU spike scenarios",
                )
            )
        
            # Step 4: Summary
            steps.append(
                PlanStep(
                    tool_name="summarize_incident",
                    call_type="tool_call",
                    input_schema={"alert_id": f"CPU spike on host {host}", "evidence": []},
                    notes="Summarize CPU spike findings",
                )
            )
    
        elif scenario == "restart_loop":
            # Step 1: Check logs
            steps.append(
                PlanStep(
                    tool_name="run_diagnostic",
                    call_type="tool_call",
                    input_schema={"host": host, "check": "startup_logs"},
                    notes=f"Inspect startup logs on host {host}",
                )
            )
    
            # Step 2: Check previous incidents
            if repeated:
                steps.append(
                    PlanStep(
                        tool_name="run_diagnostic",
                        call_type="tool_call",
                        input_schema={"host": host, "check": "compare_previous"},
                        notes=f"Compare restart-loop behaviour with previous incidents",
                    )
                )
    
            # Step 3: Restart-loop runbook
            steps.append(
                PlanStep(
                    tool_name="retrieve_runbook",
                    call_type="tool_call",
                    input_schema={"query": "service restart loop", "top_k": 1},
                    notes="Fetch runbook for repeated service restarts",
                )
            )
    
            # Step 4: Summary
            steps.append(
                PlanStep(
                    tool_name="summarize_incident",
                    call_type="tool_call",
                    input_schema={"alert_id": f"Service restart loop on host {host}", "evidence": []},
                    notes="Summarize restart-loop findings",
                )
            )
    
        # generic - service unavailale
        elif scenario == "unavailable":
            # Step 1: Check connectivity
            steps.append(
                PlanStep(
                    tool_name="run_diagnostic",
                    call_type="tool_call",
                    input_schema={"host": host, "check": "connectivity"},
                    notes=f"Check service connectivity on host {host}",
                )
            )
    
            # Step 2: Check dependent resources are healthy
            steps.append(
                PlanStep(
                    tool_name="run_diagnostic",
                    call_type="tool_call",
                    input_schema={"host": host, "check": "dependency_health"},
                    notes=f"Check dependent services for host {host}",
                )
            )
    
            # Step 3: Unavailable-service runbook
            steps.append(
                PlanStep(
                    tool_name="retrieve_runbook",
                    call_type="tool_call",
                    input_schema={"query": "service unavailable", "top_k": 1},
                    notes="Fetch runbook for service unavailability",
                )
            )
    
            # Step 4: Summary
            steps.append(
                PlanStep(
                    tool_name="summarize_incident",
                    call_type="tool_call",
                    input_schema={"alert_id": f"Service unavailable on host {host}", "evidence": []},
                    notes="Summarize service-unavailable findings",
                )
            )
    
        # other scenarios
        else:
            steps.append(
                PlanStep(
                    tool_name="retrieve_runbook",
                    call_type="tool_call",
                    input_schema={"query": "general troubleshooting", "top_k": 1},
                    notes="Fallback runbook for unknown issues",
                )
            )
            steps.append(
                PlanStep(
                    tool_name="summarize_incident",
                    call_type="tool_call",
                    input_schema={"alert_id": "Unknown issue", "evidence": []},
                    notes="Summarize unknown incident",
                )
            )
    
        return {"steps": steps}

    
    
    def _validate_plan(self, steps: List[PlanStep]) -> List[str]:
        """Validate required fields and brief notes.
    
        Returns a list of problems; empty means the plan is acceptable.
        """
    
        problems: List[str] = []  # Collected validation issues.
        if not (1 <= len(steps) <= 5):  # Keep plans short and readable.
            problems.append("plan must have 1..5 steps")
        for i, s in enumerate(steps, start=1):
            if not s.tool_name:
                problems.append(f"step {i}: missing tool_name")
            if not s.input_schema:
                problems.append(f"step {i}: missing input_schema")
            if len(s.notes.split()) > 12:
                problems.append(f"step {i}: notes too long")
        return problems
    
    @staticmethod
    def render_plan(steps: List[PlanStep]) -> str:
        """Return a numbered plan for display/logging."""
    
        lines: List[str] = []  # Output buffer.
        for i, s in enumerate(steps, start=1):
            schema_keys = list(s.input_schema.keys())  # Ordered view for display.
            # Human-readable line.
            line = f"{i}. {s.tool_name} | schema={schema_keys} | {s.notes}"
            lines.append(line)  # Accumulate.
        return "\n".join(lines)  # Single printable block.

render_plan = LLMPlanner.render_plan