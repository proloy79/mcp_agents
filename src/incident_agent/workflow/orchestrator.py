from .memory import MemoryText, Memory
from .observation  import Observation
from .planner import LLMPlanner, render_plan
import json
import logging
from .task_graph import Task, TaskResult, TaskGraph
from typing import Dict, List
  
class Orchestrator:
    def __init__(self, mcp_client):  
        self.logger = logging.getLogger(self.__class__.__name__)
        self.client=mcp_client
        self.memory = Memory()
        self.planner = LLMPlanner()
    
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
            
    async def handle_incident(self, observation: Observation) -> List[str]:
        self.logger.info(f"Incident Agent called with prompt : {observation.text}\n")
        outputs:List[Dict[str, str]] = []
        self.memory.add(f"[observation] {observation.text}")
        memory_snippet = self.memory.build_memory_snippet(query=observation.text, k=1, n=3)  
        self.logger.debug(self.client.capabilities.keys())
        alert_snapshot = await self.client.get_resource(self.client.capabilities["resources"][0]["uri"]) #assume only 1 endpoint exists for now
        tools = self._format_tools_for_prompt()
        
        planner_prompt = self._build_planner_prompt(
            observation.text,
            alert_snapshot,
            memory_snippet,
            tools)
        
        self.logger.debug(f"Planner prompt:\n---------------------------------------------------\n")
        self.logger.debug(f"{planner_prompt}\n---------------------------------------------------")
        
        # passing the memory_snippet to the fake planner will use the prompt with real llm
        plan = self.planner.plan(observation.text, memory_snippet) 

        #self.logger.info(f"Plan returned by llm is: \n{render_plan(plan["steps"])}\n")

        if "errors" in plan and plan["errors"]:            
            self.logger.info(
                "\n"
                "---------------------------------------------------\n"
                f"Payload:\n{json.dumps(step.input_schema, indent=4)}\n"
                f"Error:\n{json.dumps(plan["errors"], indent=4)}\n"
                "---------------------------------------------------"
            )            
            return  plan, []

        tasks = self._build_tasks_from_plan(plan["steps"])
        graph = TaskGraph(tasks)
        results = await graph.run(context={})
        #self.logger.debug(f"TaskGraphoutput: {results}")
        #self.logger.info('---------------------------------------------------')
        self.logger.info('Running through the PlanSteps returned by LLMPlanner')
        #self.logger.info('---------------------------------------------------')
        
        for stepNo, step in enumerate(plan["steps"], start=1):
            if step.call_type != "tool_call":
                continue
                
            #result = await self.client.call_tool(step.tool_name, step.input_schema)
            step_result = results.get(stepNo)

            if not step_result:
                self.logger.error(f"No TaskGraph result found for step {stepNo}")
                continue
                    
            for text in self._result_as_text(step.tool_name, step.input_schema, step_result.value):
                self.memory.add(text)
                outputs.append({"turn": stepNo, "tool": step.tool_name, "result": text})
                            
            
        #self.logger.debug(f"Memory snapshot: {self.memory.to_json()}")
        return plan, outputs

    def _build_planner_prompt(self, observation, alert_snapshot, memory_snippet, tools):
        """
        This will create a prompt like this for the llm planner

        -----------------------
        You are an incident response agent.

        Current observation:
        "CPU spike on host B"
        
        Alert snapshot:
        {...}
        
        Relevant memory:
        - [summary] CPU spike on host A → ...
        - [diagnostic] host=A cpu_usage → high
        
        Recent memory:
        - [observation] CPU spike on host B
        
        Available tools:
        1. run_diagnostic(host, check)
        2. retrieve_runbook(query, top_k)
        3. summarize_incident(title, signals)
        
        Based on this, produce a step-by-step plan.
        ---------------------------
        """
        
        return f"""
You are an incident response agent.

Current observation:
{observation}

Alert snapshot:
{alert_snapshot}

Relevant memory:
{memory_snippet}

Available tools:
{tools}

Based on this information, produce a step-by-step plan.
        """
        
    def _format_tools_for_prompt(self) -> str:
        lines = []
        for idx, tool in enumerate(self.client.capabilities["tools"], start=1):
            name = tool["name"]
            params = ", ".join(tool["input_schema"].keys())
            lines.append(f"{idx}. {name}({params})")
        return "\n".join(lines)
        
    def _diagnostic_as_text(self, host: str, command: str, result: dict) -> str:
        status = result.get("result", {}).get("status", "unknown")
        stdout = result.get("result", {}).get("data", {}).get("stdout", "")
        latency = result.get("result", {}).get("metrics", {}).get("latency_ms", "")
        return f"[diagnostic] host={host}, command={command} → status={status}, details={stdout}(latency={latency}ms)"
        
    def _incident_summaryc_as_text(self, summary: str, severity: str, likely_cause: str) -> str:        
        return f"[summary] {summary} severity: {severity} likely_caue: {likely_cause}"

    def _runbook_as_text(self, title: str, steps: list, confidence: float) -> str:
        step_text = " -> ".join(steps)
        return f"[runbook] {title} → {step_text} (confidence={confidence:.2f})"

    def _result_as_text(self, tool_name, arguments: dict, result: dict):   
        results = []
        if tool_name == "run_diagnostic":
            results.append(
                self._diagnostic_as_text(
                    host=arguments.get("host"),
                    command=arguments.get("check"),
                    result=result
                )
            )
    
        elif tool_name == "summarize_incident":
            results.append(
                self._incident_summaryc_as_text(
                    summary=arguments.get("summary"),
                    severity=arguments.get("severity",""),
                    likely_cause=arguments.get("likely_cause", "")
                )
            )
    
        elif tool_name == "retrieve_runbook":            
            runbooks = result.get("result",{}).get("runbooks", [])
            #self.logger.debug(f"runbooks------------------{runbooks}")
            for rb in runbooks:
                results.append(
                    self._runbook_as_text(
                        title=rb.get("title"),
                        steps=rb.get("steps", []),
                        confidence=rb.get("confidence", 0.0)
                    )
                )
        return results