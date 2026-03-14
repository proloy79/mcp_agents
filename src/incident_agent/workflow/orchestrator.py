from .memory import MemoryText, Memory
from .observation  import Observation
from .planner import LLMPlanner, render_plan
import json
import logging
from logging_config import sep
from .task_graph import Task, TaskResult, TaskGraph
from typing import Dict, List
from .context import RunContext
from .tracer import TraceEvent
from datetime import datetime, timezone

class Orchestrator:
    def __init__(self, mcp_client):  
        self.logger = logging.getLogger(self.__class__.__name__)
        self.client=mcp_client
        self.memory = Memory()
        self.planner = LLMPlanner()
    
    def _build_tasks_from_plan(self, plan_steps, ctx: RunContext) -> Dict[int, Task]:
        tasks = {}
        
        #self.logger.debug(plan_steps)
        
        for turn, step in enumerate(plan_steps, start=1): 
            # bind step at definition time
            def make_fn(step, turn):
                async def _fn(ctx):
                    ctx.trace_recorder.add(TraceEvent(
                        run_id=ctx.run_id,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        action="tool_call",
                        payload={
                            "turn": turn,
                            "tool": step.tool_name,
                            "input": step.input_schema,
                            "deps": step.deps
                        }
                    ))
                    result = {}
                    if ctx.replay_mode:
                        result = ctx.shared["queue"].next("tool_result")["payload"]["output"]
                    else:
                        result = await self.client.call_tool(step.tool_name, step.input_schema)
    
                    ctx.trace_recorder.add(TraceEvent(
                        run_id=ctx.run_id,
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        action="tool_result",
                        payload={
                            "turn": turn,
                            "tool": step.tool_name,
                            "output": result,
                        }
                    ))
                    return result
                return _fn

            tasks[turn] = Task(
                run_id=ctx.run_id,
                tool_name=step.tool_name,  
                turn=turn,
                fn=make_fn(step, turn),
                deps=step.deps,
                skip_on_error=False,
            )
            
        return tasks
            
    async def handle_incident(self, observation: Observation, ctx: RunContext) -> List[str]:
        self.logger.info(f"RunId:{ctx.run_id} - Received observation : {observation.text}\n")
        self.logger.info(f"RunId:{ctx.run_id} - Update memory with observation")
        self.memory.add(f"[observation] {observation.text}")
        
        memory_snippet = self.memory.build_memory_snippet(query=observation.text, k=1, n=3)  
        
        available_tools_summary = ""
        alert_snapshot = {}
        
        # not getting the list of resources available in replay mode
        if(not ctx.replay_mode):            
            self.logger.debug(f"RunId:{ctx.run_id} - Supported capabilities: {self.client.capabilities.keys()}")
            self.logger.info(f"RunId:{ctx.run_id} - Making resource call to server to get alert snapshot")
            alert_snapshot = await self.client.get_resource(self.client.capabilities["resources"][0]["uri"]) #assume only 1 endpoint exists for now
            
            self.logger.info(f"RunId:{ctx.run_id} - RESOURCE SNAPSHOT:\n{sep("-")}\n{alert_snapshot}\n{sep("-")}\n")
        
            available_tools_summary = self._format_tools_for_prompt()
        
        planner_prompt = self._build_planner_prompt(
            observation.text,
            alert_snapshot,
            memory_snippet,
            available_tools_summary)
        
        self.logger.debug(f"RunId:{ctx.run_id} - Planner prompt:\n{sep("-")}\n")
        self.logger.debug(f"{planner_prompt}\n{sep("-")}")

        self.logger.info(f"RunId:{ctx.run_id} - Calling LLMPlanner")
        plan = self.planner.plan(observation.text, memory_snippet)

        self.logger.info(f"Summary of plan returned by llm is: \n{render_plan(plan["steps"])}\n")

        if "errors" in plan and plan["errors"]:            
            self.logger.info(
                f"RunId:{ctx.run_id} - \n"
                "{sep("-")}\n"
                f"Observation:{observation.text}\n"
                f"Error:\n{json.dumps(plan["errors"], indent=4)}\n"
                "{sep("-")}"
            )   
            # log error and return
            ctx.trace_recorder.add(TraceEvent(
                run_id=ctx.run_id,
                timestamp = datetime.now(timezone.utc).isoformat(),                
                action = "plan",
                status = "error",
                payload = {
                    "errors": plan["errors"]                        
                }
            ))
            return  {}

        #self.logger.debug('{sep("-")}')
        self.logger.debug(f"RunId:{ctx.run_id} - Running through the PlanSteps returned by LLMPlanner")
        #self.logger.debug('{sep("-")}')
        for turn, step in enumerate(plan["steps"], start=1):
            self.logger.debug(f"Plan step [{turn}]: {step}")
            
        self.logger.info(f"RunId:{ctx.run_id} - Creating tasks from plan")        
        tasks = self._build_tasks_from_plan(plan["steps"], ctx)
        self.logger.info(f"RunId:{ctx.run_id} - Calling TaskGraph which will run each task")
        graph = TaskGraph(tasks)
        results = await graph.run(ctx)

        self.logger.debug(f"TaskGraphoutput: {results}")
        
        for turn, task_result in results.items(): 
            msg = f"{task_result}"
            self.memory.add(msg) 
            if(task_result.name == 'summarize_incident'):
                self.logger.info(
                    "Incident summary result:\n"
                    f"{sep("-")}\n"
                    "%s\n"
                    f"{sep("-")}\n"
                    "Severity: %s\n"
                    "Likely cause: %s",
                    task_result.value["result"]["summary"],
                    task_result.value["result"]["severity"],
                    task_result.value["result"]["likely_cause"],
                )

            else:
                self.logger.info(f"RunId:{ctx.run_id} - TaskResult for task({turn}) : {msg}")
            
        return results

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
        {sep("-")}--
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
        #for idx, tool in enumerate(alert_snapshot, start=1):
            name = tool["name"]
            params = ", ".join(tool["input_schema"].keys())
            lines.append(f"{idx}. {name}({params})")
        return "\n".join(lines)
        
