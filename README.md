# Incident Agent

[![Open In Colab - incident agent runner](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/proloy79/incident_agent/blob/main/notebooks/incident_agent_runner.ipynb)

This project is an example of agentic AI - a software that suggests solutions based on previous results and can take action by calling tools based on the generated plan.

It uses a LLM stub for planning, MCP tools for gathering system data, and a simple semantic memory layer to understand and suggest a multi-step action plan for infrastructure issues.

This project is a prototype that is easy to read and extend — a basic implementation of how an agent can coordinate planning, tool execution, and memory-based reasoning to handle an incident from start to finish.

The agent brings together:
- LLM driven planning to break an incident into actionable steps
(currently using a LLM stub, that can be swapped for a real one with no structural changes)
- MCP based tool execution for collecting logs, metrics, and system state data
- TaskGraph orchestration to run plan steps safely with guardrails
- Structured trace events for replay and debugging
- Semantic memory to maintain context across steps and improve reasoning. Uses the simple approach of returning the top-k entries by cosine similarity to the query vector
  
The agent can operate in two modes:
- Live Mode — the agent plans, executes tools, records traces, and responds to real incidents.
- Replay Mode — the agent replays a previously recorded trace deterministically for debugging, testing, and workflow evolution.
  

## Features

### RunContext

Every execution—live or replay—runs inside a RunContext, which holds:
- trace_recorder — captures every planner decision, tool call, and observation
- tool_spec_registry — available tool runtime params
- audit_root — where traces are written
- shared — runtime state (e.g., max_turns, cpu_ms, replay queue)
- replay_mode — toggles between Live and Replay behaviour
- run_id — unique ID for each run

### Live Mode

Live Mode is the default behaviour.

How it works
- The agent receives an incident request from the client.
- The planner generates a task graph.
- The orchestrator executes tasks, calling tools as needed.
- Each step is recorded by the tracer into a structured JSONL trace.


### Replay Mode

Replay Mode allows you to replay a previously recorded trace deterministically.

How it works
- A trace file is loaded from tests/replay/traces/....
- Events are placed into an EventQueue.
- The planner/orchestrator request the “next” event.
- Instead of executing tools, the system pops the next recorded event.
- The agent behaves as if the tool executed, but gets the output from the queue.


### Configuration

All configuration lives under configs/.
config.yaml
- global settings
- shared runtime values (max_turns, cpu_ms)
- audit/log paths
- Hydra overrides
logging/logging.yaml
- file + console handlers
- log formatting
- log levels
tools/specs/


### Tools
Tools live under src/incident_agent/tools/.
- definitions/ — static tool definitions
- handlers.py — Python implementations
- registry.py — registration + lookup
- tool_executor.py — executes tools in Live Mode
 
In Replay Mode, tool_executor is ignored and events are replayed from the replay queue.

### Replay artifacts

Location: tests/replay/traces/

Contains deterministic traces for:
- CPU spikes
- Repeated restarts
- Multi‑step incidents

## Running the Agent

Clone the repository: [incident_agent](https://github.com/proloy79/incident_agent.git)

Update the configs/config.yaml and set these accordingly:
  - replay: True/False
  - trace_file: tests/replay/traces/cpu_spike_A/audit.jsonl <i>(only used if replay is True)</i>


MCP Server:<br>
    &nbsp;&nbsp;&nbsp;&nbsp;python -m incident_agent.mcp_demo_server

Live Mode:<br>
    &nbsp;&nbsp;&nbsp;&nbsp;python src/incident_agent/main.py

Replay Mode:<br>
    &nbsp;&nbsp;&nbsp;&nbsp;python src/incident_agent/main.py replay_mode=true trace_file=tests/replay/traces/cpu_spike_A<br>
    &nbsp;&nbsp;&nbsp;&nbsp;python src/incident_agent/main.py replay_mode=true trace_file=tests/replay/traces/cpu_spike_B<br>
    &nbsp;&nbsp;&nbsp;&nbsp;python src/incident_agent/main.py replay_mode=true trace_file=tests/replay/traces/repeated_restart<br>
