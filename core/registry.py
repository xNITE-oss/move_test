"""Agent nomi -> klass. Yangi agent shu yerga bitta qator bilan qo'shiladi."""

from __future__ import annotations

import importlib
from typing import Type

from config.settings import Settings
from core.base_agent import BaseAgent
from core.rubric import RubricConfig

#: nom -> "modul:Klass"
AGENT_REGISTRY: dict[str, str] = {
    "research": "agents.research_agent:ResearchAgent",
    "writer": "agents.writer_agent:WriterAgent",
    "image": "agents.image_agent:ImageAgent",
    "audio": "agents.audio_agent:AudioAgent",
    "quality": "agents.quality_agent:QualityAgent",
    "publisher": "agents.publisher_agent:PublisherAgent",
}


class UnknownAgent(KeyError):
    pass


def resolve_agent_class(name: str) -> Type[BaseAgent]:
    try:
        target = AGENT_REGISTRY[name]
    except KeyError as exc:
        raise UnknownAgent(
            f"'{name}' nomli agent registry'da yo'q. Mavjudlari: "
            f"{', '.join(sorted(AGENT_REGISTRY))}"
        ) from exc
    module_path, class_name = target.split(":")
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def build_agent(name: str, settings: Settings, rubric: RubricConfig) -> BaseAgent:
    return resolve_agent_class(name)(settings, rubric)


def register_agent(name: str, target: str) -> None:
    """Runtime'da agent qo'shish (plugin/test uchun)."""
    AGENT_REGISTRY[name] = target
