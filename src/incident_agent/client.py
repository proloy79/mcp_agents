import logging
import asyncio # event loop support
import json # JSON serialization helper
import uuid # unique correlation IDs
import websockets # WebSocket client transport
from request_type import RequestType
from typing import Any, Dict

class Client:
    def __init__(self, endpoint, client_version="1.0.0"):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.endpoint = endpoint
        self.client_version = client_version
        self.ws = None
        self.capabilities = {}

    async def __aenter__(self):
        self.ws = await websockets.connect(self.endpoint, subprotocols=["mcp"])
        await self._initialize()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.ws.close()

    async def _initialize(self):
        params = {"clientName": "incident-agent", "clientVersion": self.client_version}
        self.capabilities = await self._send_request(RequestType.INITIALIZE, params)
        self.capabilities = self.capabilities["result"]["capabilities"]
        self.logger.info('--------------------------------------------------------------------')
        self.logger.info(json.dumps(self.capabilities, indent=4))
        self.logger.info('Handshake accepted, response received. server capabilities are: ') #, "\n\n", json.dumps(self.capabilities, indent=4), "\n")  
        tool_names = [tool["name"] for tool in self.capabilities["tools"]]
        self.logger.info(f"\tTools: {tool_names}")
        self.logger.info(f"\tResources: {self.capabilities['resources']}")
        self.logger.info('--------------------------------------------------------------------\n\n')
        
    async def _send_request(self, request_type: RequestType, params: Dict[str, Any]) -> Any:
        req_id = str(uuid.uuid4())
        payload = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": request_type.value,
            "params": params,
        }
        await self.ws.send(json.dumps(payload))
        response = await self.ws.recv()
        return json.loads(response)
        
    async def call_tool(self, name:str, arguments:str) -> Any:
        params = {"name": name, "arguments": arguments}
        return await self._send_request(RequestType.TOOL_CALL, params)

    async def get_resource(self, uri:str) -> Any:
        params = {"uri": uri}
        return await self._send_request(RequestType.GET_RESOURCE, params)
