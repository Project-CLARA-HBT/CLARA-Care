from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentContext:
    role: str
    intent: str
    metadata: dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """Interface chuẩn cho mọi agent trong CLARA."""

    name: str = "base-agent"

    @abstractmethod
    async def arun(self, query: str, ctx: AgentContext) -> dict[str, Any]:
        raise NotImplementedError
