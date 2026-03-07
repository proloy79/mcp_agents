import asyncio
from agent.incident_agent import IncidentAgent
from client import Client
from agent.observation import Observation
from logging_config import setup_logging
import logging

ENDPOINT = "ws://localhost:8765/mcp" # local MCP server address
CLIENT_VERSION="1.0.0"

async def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Incident Agent starting up...")

    async with Client(ENDPOINT, CLIENT_VERSION) as client:
        agent = IncidentAgent(client)
        observation = Observation("CPU spike on host A", 1)
        await agent.handle_incident(observation)
        observation = Observation("CPU spike on host B", 2)
        await agent.handle_incident(observation)
        observation = Observation("Repeated restart of container instance 1 in host A", 3)
        await agent.handle_incident(observation)
        
if __name__ == "__main__":
    asyncio.run(main())
