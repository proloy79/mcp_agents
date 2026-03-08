import asyncio
from workflow.edge_runner import EdgeRunner
from client import Client
from workflow.observation import Observation
from logging_config import setup_logging
import logging

ENDPOINT = "ws://localhost:8765/mcp" # "wss://operator-spoken-tracks-election.trycloudflare.com/mcp" 
CLIENT_VERSION="1.0.0"

async def main():
    setup_logging()
    logger = logging.getLogger(__name__)
    logger.info("Incident Agent starting up...")

    async with Client(ENDPOINT, CLIENT_VERSION) as client:
        edgeRunner = EdgeRunner(client)
        observation = Observation("CPU spike on host A", 1)
        output = await edgeRunner.execute(observation)
        logger.info(f"request=[{observation.text}] audit path=[{output['audit_path']}]")
        observation = Observation("CPU spike on host B", 2)
        output = await edgeRunner.execute(observation)
        logger.info(f"request=[{observation.text}] audit path=[{output['audit_path']}]")
        observation = Observation("Repeated restart of container instance 1 in host A", 3)
        output = await edgeRunner.execute(observation)
        logger.info(f"request=[{observation.text}] audit path=[{output['audit_path']}]")
        
if __name__ == "__main__":
    asyncio.run(main())
