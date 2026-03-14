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
    deps: List[int]
    
class LLMPlanner:
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        #short term memory to store every tool call result for this particular incident to avoid repeating same steps
        # self.episodic = [] 

    def plan(self, incident_text: str, memory_snippet: str) -> Dict[str, Any]:
        """
        Get the plan from LLM, validate and return
        """  
        self.logger.info(f"Preparing plan using fake llm planner")
        plan = self._fake_llm_plan(incident_text, memory_snippet)  
        self.logger.info(f"Prepared plan with {len(plan["steps"])} steps, validating each one of them")
        problems=self._validate_plan(plan["steps"])
        
        if problems:            
            return {
                "steps": [],
                "errors": problems
            } 
        self.logger.info("Plan validated successfully.")
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
                    deps=[]
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
                        deps=[1]
                    )
                )
            else:
                steps.append(
                    PlanStep(
                        tool_name="run_diagnostic",
                        call_type="tool_call",
                        input_schema={"host": host, "check": "top_processes"},
                        notes=f"Identify top CPU-consuming processes on host {host}",
                        deps=[1]
                    )
                )
        
            # Step 3: CPU runbook
            steps.append(
                PlanStep(
                    tool_name="retrieve_runbook",
                    call_type="tool_call",
                    input_schema={"query": "cpu spike", "top_k": 3},
                    notes="Fetch runbook steps for CPU spike scenarios",
                    deps=[2]
                )
            )
        
            # Step 4: Summary
            steps.append(
                PlanStep(
                    tool_name="summarize_incident",
                    call_type="tool_call",
                    input_schema={
                        "incident_type": "cpu_spike",
                        "host": host,
                        "is_repeated": repeated,
                        "evidence": [
                            {"source": "run_diagnostic", "check": "cpu_usage"},
                            {"source": "run_diagnostic", "check": "compare_previous" if repeated else "top_processes"},
                            {"source": "retrieve_runbook", "query": "cpu spike"},
                        ],
                        "summary_requirements": {
                            "include_root_cause": True,
                            "include_supporting_metrics": True,
                            "include_runbook_steps": True,
                            "include_recommended_actions": True,
                        },
                    },
                    notes="Produce a structured CPU spike summary using all diagnostic evidence and runbook guidance.",
                    deps=[3]
                )
            )
    
        elif scenario == "restart_loop":
            # Step 1: Check logs
            steps.append(
                PlanStep(
                    tool_name="run_diagnostic",
                    call_type="tool_call",
                    input_schema={"host": host, "check": "startup_logs"},
                    notes=f"Inspect startup logs on host {host} to identify failure patterns.",
                    deps=[]
                )
            )

    
            # Step 2: Check previous incidents
            if repeated:
                steps.append(
                    PlanStep(
                        tool_name="run_diagnostic",
                        call_type="tool_call",
                        input_schema={"host": host, "check": "compare_previous"},
                        notes="Compare restart-loop behaviour with previous incidents to detect recurring patterns.",
                        deps=[1]
                    )
                )
            else:
                steps.appenvd(
                    PlanStep(
                        tool_name="run_diagnostic",
                        call_type="tool_call",
                        input_schema={"host": host, "check": "service_health"},
                        notes="Check current service health and dependency status.",
                        deps=[1]
                    )
                )

    
            # Step 3: Restart-loop runbook
            steps.append(
                PlanStep(
                    tool_name="retrieve_runbook",
                    call_type="tool_call",
                    input_schema={"query": "service restart loop", "top_k": 1},
                    notes="Fetch runbook guidance for diagnosing repeated service restarts.",
                    deps=[2]
                )
            )

            # Step 4: Summary
            steps.append(
                PlanStep(
                    tool_name="summarize_incident",
                    call_type="tool_call",
                    input_schema={
                        "incident_type": "restart_loop",
                        "host": host,
                        "is_repeated": repeated,
                        "evidence": [
                            {"source": "run_diagnostic", "check": "startup_logs"},
                            {
                                "source": "run_diagnostic",
                                "check": "compare_previous" if repeated else "service_health",
                            },
                            {"source": "retrieve_runbook", "query": "service restart loop"},
                        ],
                        "summary_requirements": {
                            "include_root_cause": True,
                            "include_failure_patterns": True,
                            "include_runbook_steps": True,
                            "include_recommended_actions": True,
                            "include_recurrence_risk": repeated,
                        },
                    },
                    notes="Produce a structured summary of the restart-loop incident using diagnostic evidence and runbook guidance.",
                    deps=[3]
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
                    notes=f"Check whether the service on host {host} is reachable.",
                    deps=[]
                )
            )
    
            # Step 2: Check dependent resources are healthy
            steps.append(
                PlanStep(
                    tool_name="run_diagnostic",
                    call_type="tool_call",
                    input_schema={"host": host, "check": "dependency_health"},
                    notes=f"Check health of dependent services (DB, cache, upstream APIs) for host {host}.",
                    deps=[1]
                )
            )
    
            # Step 3: Unavailable-service runbook
            steps.append(
                PlanStep(
                    tool_name="retrieve_runbook",
                    call_type="tool_call",
                    input_schema={"query": "service unavailable", "top_k": 1},
                    notes="Fetch runbook guidance for diagnosing service unavailability.",
                    deps=[2]
                )
            )
    
            # Step 4: Summary
            steps.append(
                PlanStep(
                    tool_name="summarize_incident",
                    call_type="tool_call",
                    input_schema={
                        "incident_type": "service_unavailable",
                        "host": host,
                        "evidence": [
                            {"source": "run_diagnostic", "check": "connectivity"},
                            {"source": "run_diagnostic", "check": "dependency_health"},
                            {"source": "retrieve_runbook", "query": "service unavailable"},
                        ],
                        "summary_requirements": {
                            "include_root_cause": True,
                            "include_connectivity_findings": True,
                            "include_dependency_findings": True,
                            "include_runbook_steps": True,
                            "include_recommended_actions": True,
                            "include_impact_assessment": True,
                        },
                    },
                    notes="Produce a structured summary of the service-unavailable incident using diagnostic evidence and runbook guidance.",
                    deps=[3]
                )
            )
    
        # other scenarios
        else:
            steps.append(
                PlanStep(
                    tool_name="retrieve_runbook",
                    call_type="tool_call",
                    input_schema={"query": "general troubleshooting", "top_k": 1},
                    notes="Fetch fallback runbook for unknown or unclassified issues.",
                    deps=[]
                )
            )
            steps.append(
                PlanStep(
                    tool_name="summarize_incident",
                    call_type="tool_call",
                    input_schema={
                        "incident_type": "unknown",
                        "host": host,
                        "evidence": [
                            {"source": "retrieve_runbook", "query": "general troubleshooting"},
                        ],
                        "summary_requirements": {
                            "include_uncertainty": True,
                            "include_user_description": True,
                            "include_runbook_steps": True,
                            "include_recommended_next_actions": True,
                            "include_possible_categories": True,
                            "confidence": "low",
                        },
                    },
                    notes="Produce a structured summary for an unknown incident using fallback runbook guidance.",
                    deps=[1]
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
                self.logger.error(f"Problem: {problems[-1]}")
            if not s.input_schema:
                problems.append(f"step {i}: missing input_schema")
                self.logger.error(f"Problem: {problems[-1]}")
            if len(s.notes.split()) > 30:
                problems.append(f"step {i}: notes too long")
                self.logger.error(f"Problem: {problems[-1]}")
        
        return problems
    
    @staticmethod
    def render_plan(steps: List[PlanStep]) -> str:
        """Return a numbered plan for display/logging."""
    
        lines: List[str] = []  # Output buffer.
        for i, s in enumerate(steps, start=1):
            schema_keys = list(s.input_schema.keys())  # Ordered view for display.
            # Human-readable line.
            line = f"{i}. {s.tool_name} | schema={schema_keys} | {s.notes} | dependencies={s.deps}"
            lines.append(line)  # Accumulate.
        return "\n".join(lines)  # Single printable block.

render_plan = LLMPlanner.render_plan