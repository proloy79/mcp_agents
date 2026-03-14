from typing import Any, Dict
import json

class EventQueue:
    def __init__(self, events=None):
        self._queue = list(events) if events else []

    def push(self, event):
        self._queue.append(event)

    def next(self, action=None):
        
        if not self._queue:
                return None
        
        # no action filter return the next event in queue    
        if action is None:
            return self._queue.pop(0)

        # return the first event with matching action
        for idx, event in enumerate(self._queue):
            if event.get("action", None) == action:
                return self._queue.pop(idx)

        # if no matching event found
        raise AssertionError(f"No event found with action '{action}'")
