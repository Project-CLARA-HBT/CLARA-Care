from __future__ import annotations

import importlib
import inspect
from collections.abc import Iterable
from types import ModuleType

from clara_ml.agents.base import BaseAgent


class AgentRegistry:
    """Registry động cho đăng ký/khám phá agent."""

    def __init__(self) -> None:
        self._agents: dict[str, type[BaseAgent]] = {}

    def register(self, key: str, agent_cls: type[BaseAgent]) -> None:
        if key in self._agents:
            raise ValueError(f"Agent key already exists: {key}")
        self._agents[key] = agent_cls

    def register_class(self, key: str):
        """Decorator tiện dụng cho dynamic registration."""

        def _wrap(agent_cls: type[BaseAgent]) -> type[BaseAgent]:
            self.register(key, agent_cls)
            return agent_cls

        return _wrap

    def get(self, key: str) -> type[BaseAgent]:
        if key not in self._agents:
            raise KeyError(f"Unknown agent key: {key}")
        return self._agents[key]

    def create(self, key: str) -> BaseAgent:
        return self.get(key)()

    def keys(self) -> Iterable[str]:
        return self._agents.keys()

    def discover(self, module_names: Iterable[str]) -> int:
        """Tự động discover agent classes từ danh sách module."""
        count = 0
        for module_name in module_names:
            module = importlib.import_module(module_name)
            count += self._register_from_module(module)
        return count

    def _register_from_module(self, module: ModuleType) -> int:
        count = 0
        for _, obj in inspect.getmembers(module, inspect.isclass):
            if not issubclass(obj, BaseAgent) or obj is BaseAgent:
                continue
            key = getattr(obj, "name", "").strip()
            if not key or key == "base-agent":
                continue
            if key in self._agents:
                continue
            self._agents[key] = obj
            count += 1
        return count
