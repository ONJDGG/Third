"""Host-owned execution bounds. No configuration may come from retrieved text."""
from dataclasses import dataclass
import math

from .protocol import ProtocolError, integer


@dataclass(frozen=True)
class Limits:
    decisions: int = 10
    tools: int = 8
    requests: int = 20
    task_seconds: float = 300
    call_seconds: float = 90
    context_chars: int = 60000
    response_bytes: int = 262144
    retries: int = 1

    def __post_init__(self):
        for name, low, high in (("decisions", 1, 50), ("tools", 1, 40),
                                ("requests", 1, 100), ("retries", 0, 2),
                                ("context_chars", 2000, 200000),
                                ("response_bytes", 1024, 1048576)):
            integer(getattr(self, name), low, high)
        for name in ("task_seconds", "call_seconds"):
            value = getattr(self, name)
            if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 3600:
                raise ProtocolError("invalid_timeout")
