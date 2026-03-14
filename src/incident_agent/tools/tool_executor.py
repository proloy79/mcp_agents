from __future__ import annotations  # Future‑proof typing of annotations.
import asyncio
import threading  # Run work in a separate thread to support timeouts.
import time  # Measure latency and implement backoff.
from dataclasses import dataclass  # Lightweight data containers.
from typing import Any, Callable, Dict, Tuple  # Type hints for clarity.
import logging

class CircuitBreaker:
    """
    On each failure append timestamp.
    Remove timestamps older than 60 seconds.
    If ≥ max_failures failures in the window -> open circuit for cooldown.
    If circuit is open -> reject calls immediately.
    After cooldown -> allow one test call -> if still fails restart cooldown
    """
    def __init__(self, max_failures=3, window_seconds=60, cooldown_seconds=60):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.cooldown_seconds = cooldown_seconds

        self.failure_timestamps = []
        self.circuit_open_until: Optional[float] = None

    def is_open(self) -> bool:
        if self.circuit_open_until is None:
            return False
        if time.time() >= self.circuit_open_until:
            self.circuit_open_until = None
            self.failure_timestamps.clear()
            return False
        self.logger.warn('Circuit is open')
        return True

    def record_failure(self):
        now = time.time()
        self.failure_timestamps.append(now)

        # Only keep failures that happened within the window
        cutoff = now - self.window_seconds
        self.failure_timestamps = [ts for ts in self.failure_timestamps if ts >= cutoff]

        # if no of failures >= max allowed within a window then extend by cool down period
        if len(self.failure_timestamps) >= self.max_failures:
            self.logger.warn(f"no of failures({len(self.failure_timestamps)}) >= max allowed({self.max_failures}) within a window.Set the circuit to open")
            self.circuit_open_until = now + self.cooldown_seconds

class ToolExecutor:
    def __init__(self, definition, spec, breaker, mcp_client):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.definition = definition
        self.spec = spec
        self.breaker = breaker
        self.client = mcp_client

    async def call_tool(self, payload):
        self.logger.debug(f"Validate payload : {payload} against run spec: {self.spec.arguments}")
        validation_error = self._validate_payload(payload, self.spec.arguments)
        if validation_error:
            self.logger.warn("Validation failed")
            return self._format_call_tool_result(validation_error, "error", 0)
            
        # check circuit breaker state
        if self.breaker.is_open():
            self.logger.info("Circuit is open, not processing")
            return self._format_call_tool_result("circuit open", "error", 0)
        
        attempts = 0  # Count attempts including the first try.
        backoff = self.spec.backoff_ms / 1000.0  # Convert ms → seconds.
        start_total = time.perf_counter()  # Time the whole call (retries included).

        while True:
            attempts += 1
            
            # check timeout
            self.logger.debug(f"{self.definition} \n {payload}")
            ok, value = await self._call_with_timeout(self.definition.handler, timeout_ms=self.spec.timeout_ms, payload=payload)
            
            if ok:  # Success: package result with status + latency.                
                return self._format_call_tool_result(value, "ok", (time.perf_counter() - start_total))

            self.logger.warn(f"Attempt no: {attempts} failed. Err: {value}. Record failure in circuit breaker")
            # register failure in circuit breaker
            self.breaker.record_failure()
    
            if self.breaker.is_open():     
                self.logger.debug('Circuit is open returning error')
                return self._format_call_tool_result("circuit open", "error", (time.perf_counter() - start_total))

            # check for max retries breach
            if attempts > self.spec.max_retries: 
                self.logger.debug('Max retries exceeded, returning error')
                return self._format_call_tool_result(value, "error", (time.perf_counter() - start_total))
            
            # apply exponential backoff    
            self.logger.debug(f"Applying exponential back off of {backoff} secs")
            time.sleep(backoff)  # Short wait before the next attempt.
            backoff *= 2  # Exponential backoff to reduce load.
            
        return await self.client.call_tool(self.spec.name, payload)
        
    def _validate_payload(self, payload: Dict[str, Any], schema: Dict[str, Any]) -> Optional[str]:
        required = schema.get("required", [])
        missing = [key for key in required if key not in payload]
    
        if missing:
            print("\nKeys missing in payload:", payload)
            print("Expected required keys:", required, "Payload keys:", payload.keys(), "\n")
            return f"Missing required fields: {', '.join(missing)}"
    
        return None
        
    async def _call_with_timeout(self, fn, *, timeout_ms: int, **kwargs) -> Tuple[bool, Any]:
        """Run the function in a thread and wait up to timeout_ms.
    
        Returns (ok, result_or_error).
        """
        try:
            result = await asyncio.wait_for(
                fn(**kwargs),
                timeout=timeout_ms / 1000.0
            )
            return True, result
        except asyncio.TimeoutError:
            return False, f"timeout after {timeout_ms} ms"
        except Exception as exc:
            self.logger.exception(exc)
            return False, str(exc)
            
    def _format_call_tool_result(self, result: str, status: str, latency_ms: int):
        self.logger.info(f"in format: {result}")
        return {
                    "result": result,
                    "status": status,
                    "latency_ms": int(latency_ms * 1000),
                }