from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import AsyncIterator, Optional, Protocol


class InputEventType(str, Enum):
    TEXT = "text"
    SHUTDOWN = "shutdown"


@dataclass(frozen=True)
class InputEvent:
    type: InputEventType
    text: Optional[str] = None
    metadata: dict[str, str] = field(default_factory=dict)


class InputSource(Protocol):
    async def events(self) -> AsyncIterator[InputEvent]:
        ...
