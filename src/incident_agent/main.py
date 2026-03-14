from typing import List, Dict, Any
import asyncio
import logging
import json
import hydra
import os
from omegaconf import DictConfig
from logging_config import setup_logging, sep
from client import Client
from incident_agent.workflow import Observation, RunContext, EdgeRunner, TraceWriter, TraceRecorder, EventQueue, InMemoryTraceWriter
from incident_agent.tools import build_tool_spec_registry, ToolSpecRegistry

#ENDPOINT = "ws://localhost:8765/mcp" # "wss://operator-spoken-tracks-election.trycloudflare.com/mcp" 
CLIENT_VERSION="1.0.0"

async def run(cfg: DictConfig):
    setup_logging(cfg)
    logger = logging.getLogger(__name__)

    tool_spec_registry = build_tool_spec_registry(cfg)
    
    if cfg.replay:
        logger.info("Replaying stored messages...")

        trace_writer = InMemoryTraceWriter()
        trace_recorder = TraceRecorder(trace_writer)
        
        ctx = RunContext(trace_recorder=trace_recorder, 
                     tool_spec_registry=tool_spec_registry, 
                     audit_root=cfg.audit_root,
                     shared=dict(cfg.shared),
                     replay_mode=True)
        
        events = load_replay_transcript(cfg.trace_file)
        queue = EventQueue(events)
        ctx.shared["queue"] = queue
        event = queue.next()
        
        prompt = event["payload"]["text"]
        logger.info(f"Replayed user prompt: {prompt}")
        
        observation = Observation(prompt)
        edgeRunner = EdgeRunner(mcp_client=None)
        
        output = await edgeRunner.execute(observation, ctx)
        trace_recorder.validate(events, cfg.trace_file, ignore_fields=["timestamp","run_id"])
        
    else:
        logger.info("Starting incident agent(live mode)...")
        async with Client(cfg.mcp_endpoint, CLIENT_VERSION) as client:
            prompt = "CPU spike on host A"
            output = await run_live(client, prompt, cfg, tool_spec_registry)
            logger.info(f"\n{sep("-")}\nUser prompt: '{prompt}'  audit path: [{output['audit_path']}]\n{sep("-")}\n")
            text = "CPU spike on host B"
            output = await run_live(client, prompt, cfg, tool_spec_registry)
            logger.info(f"\n{sep("-")}\nUser prompt: '{prompt}'  audit path: [{output['audit_path']}]\n{sep("-")}\n")
            text = "Repeated restart of container instance 1 in host A"
            output = await run_live(client, prompt, cfg, tool_spec_registry)
            logger.info(f"\n{sep("-")}\nUser prompt: '{prompt}'  audit path: [{output['audit_path']}]\n{sep("-")}\n")
        

async def run_live(client: Client, prompt: str, cfg: DictConfig, tool_spec_registry: ToolSpecRegistry) -> Dict[str, any]:
    
    trace_writer = TraceWriter(path=cfg.audit_root)
    trace_recorder = TraceRecorder(trace_writer)
    edgeRunner = EdgeRunner(client)
    
    ctx = RunContext(trace_recorder=trace_recorder, 
                     tool_spec_registry=tool_spec_registry, 
                     audit_root=cfg.audit_root,
                     shared=dict(cfg.shared),
                     replay_mode=False)
       
    observation = Observation(prompt)
    return await edgeRunner.execute(observation, ctx)
    
def load_replay_transcript(trace_file: str) -> List[Dict[str, Any]]:
    events = []
    trace_file = os.path.expanduser(trace_file)
    
    with open(trace_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            print(line)
            events.append(json.loads(line))
    return events
                
@hydra.main(config_path="../../configs", config_name="config", version_base=None)
def main(cfg: DictConfig):
    asyncio.run(run(cfg))

if __name__ == "__main__":
    main()
