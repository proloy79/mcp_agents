from dataclasses import dataclass

@dataclass
class Observation:
    """Container for a single turn’s input."""

    text: str  # Natural-language description of the task or signal.