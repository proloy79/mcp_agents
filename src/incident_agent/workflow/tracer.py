from __future__ import annotations  # Future-proof typing.

import json  # Write a compact audit file.
import os  # Join paths.
import tempfile  # Ephemeral sandbox directory.
import time  # CPU guard.
from typing import Protocol
import logging
from logging_config import sep
import uuid
from dataclasses import dataclass, asdict 
from datetime import datetime, timezone
import json


@dataclass
class TraceEvent:
    run_id: int
    timestamp: str
    action: str
    payload: dict
    status: str ="ok"

class Writer(Protocol):
    def write(self, event: TraceEvent) -> None:
        ...
        
class TraceWriter:
    def __init__(self, path: str):
        self.path = path
        self.f = None

    def _ensure_open(self):
        if self.f is None:
            # "a" mode creates the file if it doesn't exist
            self.f = open(self.path, "a", encoding="utf-8")

    def write(self, event):
        try:
            self._ensure_open()
            self.f.write(json.dumps(asdict(event)) + "\n")
        except Exception:
            pass

    def close(self):
        try:
            if self.f:
                self.f.close()
        except Exception:
            pass
        finally:
            self.f = None


class InMemoryTraceWriter():
    def write(self, event: TraceEvent):
        pass

    def close(self):
        pass

class TraceReader:
    def read_trace(self, path):
        events = []
        with open(path, "r") as f:
            for line in f:
                events.append(json.loads(line))
        return events 

class TraceRecorder:
    def __init__(self, trace_writer: Writer):
        self.events = []
        self.trace_writer = trace_writer

    def add(self, event: TraceEvent):
        self.events.append(event)

    def to_jsonl(self):
        return "\n".join(e.to_json() for e in self.events)

class TraceRecorder:
    def __init__(self, trace_writer: Writer):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.events = []
        self.trace_writer = trace_writer

    def add(self, event: TraceEvent):
        self.events.append(event)

    def to_jsonl(self):
        return "\n".join(e.to_json() for e in self.events)

    def validate(
        self,
        events_from_replay: List[Dict[str, Any]],
        trace_file: str,
        ignore_fields=[]
    ):
        """
        Validate that recorded events match replayed events.
        ignore_fields: list of keys to skip during comparison.
        """
        self.logger.info(f"\n\n{sep("=")}\nValidating replay results for trace file : {trace_file}\n")
        ignore_fields = set(ignore_fields)

        # 1. Length check
        if len(self.events) != len(events_from_replay):
            msg = (
                f"Validation FAILED: event count mismatch\n"
                f"   original={len(self.events)}, replay={len(events_from_replay)}"
            )
            self.logger.error(msg)
            self.logger.info(f"\n{sep("=")}");
            raise ValueError(msg)

        # 2. Compare event-by-event
        for idx, (orig_event, replay_event) in enumerate(zip(self.events, events_from_replay)):
            orig_dict = asdict(orig_event)

            for key, orig_val in orig_dict.items():
                if key in ignore_fields:
                    continue

                replay_val = replay_event.get(key)

                if orig_val != replay_val:
                    msg = (
                        f"Validation FAILED at event {idx}, field '{key}'\n"
                        f"   original: {orig_val}\n"
                        f"   replay:   {replay_val}"
                    )
                    self.logger.error(msg)
                    self.logger.info(f"\n{sep("=", 100)}");
                    raise ValueError(msg)

        self.logger.info(f"Replay SUCCESSFULL: All events match\n{sep("=")}");