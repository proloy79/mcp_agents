import time
import logging

_logger=logging.getLogger()

async def retrieve_runbook_handler(payload: dict) -> dict:
    query = (payload.get("query") or "").lower()
    top_k = payload.get("top_k", 1)

    RUNBOOKS = {
        "cpu": [
            {
                "title": "CPU Spike",
                "steps": [
                    "Check CPU usage",
                    "Inspect top processes",
                    "Restart service if needed",
                    "Verify load balancer distribution"
                ],
                "confidence": 0.91,
            }
        ],
        "restart_loop": [
            {
                "title": "Service Restart Loop",
                "steps": [
                    "Check recent logs for startup errors",
                    "Verify configuration files and environment variables",
                    "Inspect recent deployments or config changes",
                    "Ensure dependent services are reachable",
                    "Restart the service manually and observe behaviour"
                ],
                "confidence": 0.89,
            }
        ],
        "default": [
            {
                "title": "General Troubleshooting",
                "steps": [
                    "Check logs",
                    "Verify configuration",
                    "Restart service",
                    "Escalate if issue persists"
                ],
                "confidence": 0.75,
            }
        ]
    }

    if "cpu" in query:
        selected = RUNBOOKS["cpu"]
    elif "restart" in query or "loop" in query or "crash" in query:
        selected = RUNBOOKS["restart_loop"]
    else:
        selected = RUNBOOKS["default"]

    return {"runbooks": selected[:top_k]}

async def run_diagnostic_handler(payload: dict) -> dict:
    host = payload.get("host")
    check = payload.get("check")

    # Fake latency
    latency = round(time.perf_counter() % 0.02, 4)

    # Hardcoded diagnostic outputs
    if check == "cpu_usage":
        output = f"CPU usage on host {host} is 92%"
    elif check == "top_processes":
        output = f"Top processes on host {host}: riskengine(55%), reporter(30%), nginx(12%)"
    elif check == "compare_previous":
        output = f"Current CPU usage on host {host} is similar to previous incident"
    else:
        output = f"Unknown diagnostic check '{check}'"

    return {
        "status": "ok",
        "data": {
            "host": host,
            "check": check,
            "stdout": output,
        },
        "metrics": {
            "latency_ms": latency * 1000
        },
    }    



async def summarize_incident_handler(payload: dict) -> dict:
    alert_id = payload.get("alert_id", "UNKNOWN")
    evidence = payload.get("evidence", [])

    # Build the summary
    lines = [
        f"Incident Summary for alert {alert_id}",
        "",
        "Evidence collected:"
    ]

    stdout_texts = []
    for item in evidence:
        tool = item.get("tool")
        result = item.get("result", {})
        stdout = result.get("data", {}).get("stdout", "")
        stdout_texts.append(stdout)
        lines.append(f"- {tool}: {stdout}")

    summary_text = "\n".join(lines)

    severity = "medium"
    likely_cause = "unknown"

    combined = " ".join(stdout_texts).lower()

    if "95%" in combined or "92%" in combined:
        severity = "high"
    if "python" in combined:
        likely_cause = "python process"
    if "db" in combined:
        likely_cause = "database load"

    return {
        "summary": summary_text,
        "severity": severity,
        "likely_cause": likely_cause,
    }
    