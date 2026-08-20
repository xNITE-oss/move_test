"""Barcha agentlar uchun umumiy interfeys.

Yangi agent qo'shish uchun:
  1. `agents/` ichida BaseAgent'dan meros olgan klass yozing;
  2. `core/registry.py` dagi AGENT_REGISTRY ga qo'shing;
  3. rubrika YAML ichida `pipeline` va `agents:` bo'limiga nom qo'shing.
Boshqa hech qanday joyga tegish shart emas.
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Any

from config.settings import Settings
from core.context import PostContext, PostStatus
from core.rubric import RubricConfig


class AgentError(RuntimeError):
    """Agent bajarilishida yuzaga kelgan xato."""


class AgentSkip(Exception):
    """Agent o'zini ataylab o'tkazib yuborishi kerak bo'lganda."""


class BaseAgent(ABC):
    #: pipeline va rubrika config'ida ishlatiladigan nom
    name: str = "agent"
    #: True bo'lsa — xato bo'lsa ham pipeline to'xtamaydi (masalan rasm/audio)
    optional: bool = False
    #: agent hali implement qilinmagan bo'lsa
    implemented: bool = True

    def __init__(self, settings: Settings, rubric: RubricConfig) -> None:
        self.settings = settings
        self.rubric = rubric
        self.cfg: dict[str, Any] = rubric.agent_cfg(self.name)
        self.log = logging.getLogger(f"agent.{self.name}")

    # -- hayot sikli ---------------------------------------------------------
    def is_enabled(self) -> bool:
        return self.rubric.is_agent_enabled(self.name)

    @abstractmethod
    async def run(self, ctx: PostContext) -> PostContext:
        """Asosiy mantiq. ctx'ni boyitib qaytaradi."""

    async def execute(self, ctx: PostContext) -> PostContext:
        """Pipeline shu metodni chaqiradi: logging + xato boshqaruvi."""
        if not self.is_enabled():
            self.log.info("o'tkazib yuborildi (config'da o'chirilgan)")
            ctx.log_step(self.name, "disabled", 0)
            return ctx

        started = time.perf_counter()
        try:
            ctx = await self.run(ctx)
            took = int((time.perf_counter() - started) * 1000)
            ctx.log_step(self.name, "ok", took)
            self.log.info("bajarildi (%d ms)", took)
            return ctx
        except AgentSkip as exc:
            took = int((time.perf_counter() - started) * 1000)
            ctx.log_step(self.name, "skipped", took, str(exc))
            self.log.info("o'tkazib yuborildi: %s", exc)
            return ctx
        except Exception as exc:  # noqa: BLE001
            took = int((time.perf_counter() - started) * 1000)
            ctx.add_error(self.name, str(exc))
            ctx.log_step(self.name, "error", took, str(exc))
            if self.optional:
                self.log.warning("xato (ixtiyoriy agent, davom etamiz): %s", exc)
                return ctx
            ctx.status = PostStatus.FAILED
            self.log.error("xato: %s", exc, exc_info=True)
            raise AgentError(f"{self.name}: {exc}") from exc

    # -- yordamchi -----------------------------------------------------------
    def opt(self, key: str, default: Any = None) -> Any:
        return self.cfg.get(key, default)


class NotImplementedAgent(BaseAgent):
    """Skeleton agentlar uchun asos.

    Config'da yoqib qo'yilgan bo'lsa — tushunarli xato beradi,
    o'chirilgan bo'lsa — jim o'tkazib yuboriladi.
    """

    implemented = False
    todo: str = "Bu agent hali implement qilinmagan."

    async def run(self, ctx: PostContext) -> PostContext:  # pragma: no cover
        raise AgentError(self.todo)
