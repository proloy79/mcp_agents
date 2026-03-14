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



def _format_evidence_item(item):
    """Convert evidence dicts into readable bullet points."""
    if isinstance(item, dict):
        parts = []
        for k, v in item.items():
            parts.append(f"{k}: {v}")
        return ", ".join(parts)
    return str(item)


async def summarize_incident_handler(payload: dict) -> dict:
    alert_id = payload.get("alert_id", "UNKNOWN")
    evidence = payload.get("evidence", [])
    req = payload.get("summary_requirements", {})

    _logger.debug(f"summarize_incident_handler -> payload={payload}")

    text_tokens = []
    for item in evidence:
        if isinstance(item, dict):
            for v in item.values():
                if isinstance(v, str):
                    text_tokens.append(v.lower())
        elif isinstance(item, str):
            text_tokens.append(item.lower())

    combined = " ".join(text_tokens)

    severity = "medium"
    if any(x in combined for x in ["95%", "92%", "cpu spike", "high cpu"]):
        severity = "high"

    likely_cause = "unknown"
    if "cpu spike" in combined:
        likely_cause = "cpu overload"
    elif "python" in combined:
        likely_cause = "python process"
    elif "db" in combined:
        likely_cause = "database load"

    lines = [
        f"Incident Summary for alert {alert_id}",
        "",
        "Evidence collected:"
    ]

    for item in evidence:
        formatted = _format_evidence_item(item)
        lines.append(f"- {formatted}")

    if req.get("include_root_cause") and likely_cause != "unknown":
        lines.append("")
        lines.append(f"Likely root cause: {likely_cause}")

    if req.get("include_recommended_actions"):
        lines.append("")
        lines.append("Recommended next actions:")
        if likely_cause == "cpu overload":
            lines.append("- Check top CPU-consuming processes")
            lines.append("- Validate autoscaling or load distribution")
        elif likely_cause == "database load":
            lines.append("- Inspect slow queries")
            lines.append("- Check DB connection saturation")
        else:
            lines.append("- Continue investigation based on new evidence")

    summary_text = "\n".join(lines)
    
    return {
        "summary": summary_text,
        "severity": severity,
        "likely_cause": likely_cause,
    }
    