import time
import logging
from typing import Any, Dict, List, Optional, Set, Callable
from .context import RunContext
from dataclasses import dataclass
from typing import Any

class Task:
    def __init__(
        self,
        run_id: str,
        turn: int,
        tool_name: str,        
        fn: Callable,          # Already includes retries/backoff/CB inside tool executor
        deps: List[str],
        skip_on_error: bool = False,
    ):
        self.run_id = run_id
        self.turn = turn
        self.tool_name = tool_name
        self.fn = fn
        self.deps = deps
        self.skip_on_error = skip_on_error


@dataclass
class TaskResult:
    name: str
    turn: int
    status: str
    latency_ms: int
    message: str
    value: Any = None



class TaskGraph:
    def __init__(self, tasks: Dict[int, Task]):
        self.logger = logging.getLogger(__name__)
        self.tasks = tasks
        self.results: Dict[int, TaskResult] = {}        

    def _check_acyclic(self) -> None:
        seen: Set[str] = set()
        stack: Set[str] = set()

        def dfs(n: str) -> None:
            if n in stack:
                raise ValueError(f"cycle detected at {n}")
            if n in seen:
                return

            stack.add(n)
            for d in self.tasks[n].deps:
                if d not in self.tasks:
                    raise KeyError(f"unknown dependency: {d}")
                dfs(d)
            stack.remove(n)
            seen.add(n)

        for name in self.tasks:
            dfs(name)
       
    def _ready(self, ctx) -> List[str]:
        """
        Determine which tasks are ready to run 
        """
        self.logger.info(f"RunId:{ctx.run_id} - Determine which tasks are ready to run ");
        ready = []
        for turn, task in self.tasks.items():
            
            self.logger.debug(f"RunId:{ctx.run_id} - Checking if task({task.tool_name})[{turn}]  with dependencies: {task.deps} is ready")
            
            if task.turn in self.results:
                self.logger.debug(f"RunId:{ctx.run_id} - Task({task.tool_name})[{turn}] already completed - ignore")
                continue
            
            self.logger.debug(f"RunId:{ctx.run_id} - Checking if all dependencies for task({task.tool_name})[{turn}] have been processed")
            
            # All deps must be completed
            if not all(d in self.results for d in task.deps):
                self.logger.debug(f"RunId:{ctx.run_id} - Not all Task({task.tool_name})[{turn}] dependencies completed - ignore {task.deps}")
                continue
            
            self.logger.debug(f"RunId:{ctx.run_id} - All dependencies for task({task.tool_name})[{turn}] have been processed, checking for failures")
            
            # If any dep failed and skip_on_error=False, block
            if not task.skip_on_error:
                if any(self.results[d].status == "error" for d in task.deps):
                    self.logger.debug(f"RunId:{ctx.run_id} - Dependencies completed with error - ignore")
                    continue
                    
            self.logger.debug(f"RunId:{ctx.run_id} - Task({task.tool_name})[{turn}] is ready")
            ready.append(turn)

        return ready

    async def run(self, ctx: RunContext) -> Dict[str, TaskResult]:
        self.logger.info(f"RunId:{ctx.run_id} - TaskGraph starting execution")
        self.logger.debug(f"RunId:{ctx.run_id} - Task keys: {self.tasks.keys()}")
        
        cpu_start = time.process_time()  # Start CPU timer.
        pending = set(self.tasks.keys())
                
        while pending:
            ran_any = False

            for turn in list(pending):
                if turn not in self._ready(ctx):
                    self.logger.info(f"RunId:{ctx.run_id} - Task({turn}) not ready, skipping")
                    continue
                
                self.logger.info(f"task[{turn}] is ready to be processed...")
                
                task = self.tasks[turn]
                
                self.logger.info(f"RunId:{ctx.run_id} - Running task for step no {turn}")

                start = time.perf_counter()

                try:

                    if "max_turns" in ctx.shared and turn > ctx.shared["max_turns"]:
                        raise RuntimeError(f"Invalid plan, max turns ({ctx.shared["max_turns"]}) exceeded")
                    
                    # CPU guard: stop if over CPU budget.
                    if "cpu_ms" in ctx.shared and int((time.process_time() - cpu_start) * 1000) > ctx.shared["cpu_ms"]:
                        raise RuntimeError(f"CPU budget ({ctx.shared["cpu_ms"]} ms) breached")

                    self.logger.debug(f"RunId:{ctx.run_id} - Making the tool call...")
                    # retries/backoff/CB appled inside task.fn
                    out = await task.fn(ctx)
                    latency_ms = int((time.perf_counter() - start) * 1000)

                    self.logger.info(f"RunId:{ctx.run_id} - Task succeeded for step no {turn}")
                    self.logger.debug(f"RunId:{ctx.run_id} - Output for step no {turn}: {out}")

                    self.results[turn] = TaskResult(
                        name=task.tool_name,
                        turn=turn,
                        status="ok",
                        latency_ms=latency_ms,
                        message="ok",
                        value = out,
                    )

                except Exception as e:
                    latency_ms = int((time.perf_counter() - start) * 1000)
                    self.logger.exception(f"RunId:{ctx.run_id} - Task failed: step no={turn} error={e}")

                    self.results[turn] = TaskResult(
                        name=task.tool_name,
                        turn=turn,
                        status="error",
                        latency_ms=latency_ms,
                        message=str(e),
                    )

                pending.remove(turn)
                ran_any = True

            if not ran_any:
                self.logger.error(f"RunId:{ctx.run_id} - Deadlock detected — marking remaining tasks as skipped")
                for turn in list(pending):
                    self.results[turn] = TaskResult(
                        name="",
                        turn=0,
                        status="skipped",
                        latency_ms=0,
                        message=f"blocked by upstream",
                    )
                    pending.remove(turn)

        self.logger.info(f"RunId:{ctx.run_id} - TaskGraph completed")
        
        return self.results