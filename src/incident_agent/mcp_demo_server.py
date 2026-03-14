import asyncio # async event loop primitives
import json # encode/decode JSON-RPC messages
import time # fake latency measurements
import websockets # WebSocket server utilities
from request_type import RequestType
from logging_config import setup_logging
import logging
import hydra
from omegaconf import DictConfig
from incident_agent.tools import ToolDefinitionRegistry, build_tool_spec_registry, ToolSpecRegistry, ToolExecutionRegistry
from incident_agent.tools.definitions import RUN_DIAGNOSTIC_DEF, RETRIEVE_RUNBOOK_DEF, SUMMARIZE_INCIDENT_DEF

HOST = "127.0.0.1" # bind to localhost only
PORT = 8765 # default MCP demo port

RUNBOOK_SNIPPETS = [ # canned runbook guidance
    "Restart the service if CPU > 90% for 5 minutes.", # first tip
    "If pods crashloop, capture logs before redeploying.", # second tip
    "If service unavaiale, try restarting first.",
] # end runbook list

CPU_SPIKE_ALERT_PAYLOAD = { # representative alert object
    "id": "ALRT-2025-10",
    "service": "staging-api",
    "symptom": "CPU spike on node-3",
    "severity": "high",
} # end alert object

CRASHLOOP_ALERT_PAYLOAD = {
    "id": "ALRT-2025-11",
    "service": "risk_engine",
    "symptom": "Service restart loop detected",
    "severity": "medium",
}

GENERIC_ALERT_PAYLOAD = {
    "id": "ALRT-2025-12",
    "service": "app-insights",
    "symptom": "Service unavailable",
    "severity": "low",
}


class MCPDemoServer:
    def __init__(self, cfg: DictConfig):
        setup_logging(cfg)
        self.logger = logging.getLogger(__name__)
        self._tool_spec_registry = None
        self._tool_def_registry = None

    def _build_capabilities(self):
        return {
            "tools": [
                {
                    "name": tool.metadata.name,
                    "description": tool.metadata.description,
                    "input_schema": tool.input_schema,
                    "output_schema": tool.output_schema,
                }
                for tool in self._tool_def_registry.all_definitions()
            ],
            "resources": [
                {
                    "uri": "memory://alerts/latest",
                    "description": "Latest alert snapshot",
                }
            ],
        }

    async def handle_session(self, ws): # process each client connection
        execution_registry = ToolExecutionRegistry(
            self._tool_def_registry,
            self._tool_spec_registry,
            ws)
    
        async for raw in ws: # stream incoming JSON-RPC frames
            req = json.loads(raw) # parse request payload
            method = RequestType(req.get("method")) # requested RPC method
            req_id = req.get("id") # correlate replies
            
            if method == RequestType.INITIALIZE: # capability handshake
                capabilities = self._build_capabilities()
                result = {"capabilities": capabilities} # send tool/resource list
            elif method == RequestType.GET_RESOURCE: # resource fetch
                args = req.get("params", {}).get("arguments", {}) # extract args
                self.logger.debug(f"args={args}")
                payload = {}
                if "cpu" in args:
                    payload = CPU_SPIKE_ALERT_PAYLOAD
                elif "restart" in args or "loop" in args or "crash" in args:
                    payload = CRASHLOOP_ALERT_PAYLOAD
                else:
                    payload = GENERIC_ALERT_PAYLOAD
                    
                result = {
                    "uri": "memory://alerts/latest",
                    "data": {
                        "alert": payload,
                        "recommendations": RUNBOOK_SNIPPETS,
                    },
                } # latest alert snapshot
            elif method == RequestType.TOOL_CALL: # tool invocation
                self.logger.debug(f"received request: {req}")
                args = req.get("params", {}).get("arguments", {}) # extract args
                tool_name = req["params"]["name"]
                result = await execution_registry.execute(tool_name, args)
                #self.logger.info(f"tool cal return: {json.dumps(result,indent=4)}")
            else:
                error = {
                    "code": -32601,
                    "message": f"Unknown method: {method}",
                } # signal unsupported method
                await ws.send(json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": error,
                    }
                )) # return JSON-RPC error
                continue # skip to next frame
                
            payload = {"jsonrpc": "2.0", "id": req_id, "result": result.get("result",result)} # success   
            await ws.send(json.dumps(payload)) # send response frame

    async def run(self, cfg: DictConfig): # run the websocket server forever
        
        self.logger.info("Starting MCP Demo server...")
    
        self._tool_spec_registry = build_tool_spec_registry(cfg)
        self._tool_def_registry = ToolDefinitionRegistry()
        self._tool_def_registry.register("run_diagnostic", RUN_DIAGNOSTIC_DEF)
        self._tool_def_registry.register("retrieve_runbook", RETRIEVE_RUNBOOK_DEF)
        self._tool_def_registry.register("summarize_incident", SUMMARIZE_INCIDENT_DEF)
    
        async with websockets.serve( # expose MCP endpoint
            self.handle_session,
            HOST,
            PORT,
            subprotocols=["mcp"],
        ):
            self.logger.info(f"MCP demo server ready on ws://{HOST}:{PORT}/mcp") # status log
            await asyncio.Future() # keep server alive indefinitely

@hydra.main(config_path="../../configs", config_name="config", version_base=None)
def main(cfg: DictConfig):
    mcp_server = MCPDemoServer(cfg)
    asyncio.run(mcp_server.run(cfg))

if __name__ == "__main__":
    main()