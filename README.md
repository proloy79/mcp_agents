# incident-agent

[![Open In Colab - incident agent runner](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/proloy79/incident_agent/blob/main/notebooks/incident_agent_runner.ipynb)

A small, end-to-end example of an autonomous incident-response agent.

It uses a lightweight (fake) LLM for planning, MCP tools for gathering system data, and a simple semantic memory layer to reason about and summarise infrastructure issues.

This project is meant to be easy to read and easy to extend — a minimal reference implementation of how an agent can coordinate planning, tool execution, and structured reasoning to handle an incident from start to finish.

The agent brings together:
- LLM driven planning to break an incident into actionable steps
(currently using a fake LLM, but you can swap in a real one with no structural changes)
- MCP based tool execution for collecting logs, metrics, and system state
- TaskGraph orchestration to run plan steps safely with guardrails
- Structured trace events for replay, debugging, and automated testing
- Semantic memory to maintain context across steps and improve reasoning

