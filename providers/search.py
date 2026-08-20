"""Web qidiruv provayderlari."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod

import httpx

from config.settings import Settings, get_settings
from core.context import Source

log = logging.getLogger("provider.search")


class SearchProvider(ABC):
    name = "base"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @abstractmethod
    async def search(
        self, query: str, *, max_results: int = 5, recency_days: int | None = None
    ) -> list[Source]:
        ...


class TavilySearchProvider(SearchProvider):
    """https://tavily.com — AI agentlar uchun qidiruv API."""

    name = "tavily"
    API_URL = "https://api.tavily.com/search"

    async def search(
        self, query: str, *, max_results: int = 5, recency_days: int | None = None
    ) -> list[Source]:
        self.settings.require("tavily_api_key")
        payload: dict = {
            "query": query,
            "max_results": max_results,
            "search_depth": "advanced",
            "include_answer": False,
        }
        if recency_days:
            payload["days"] = recency_days
            payload["topic"] = "news"

        async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
            resp = await client.post(
                self.API_URL,
                headers={"Authorization": f"Bearer {self.settings.tavily_api_key}"},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        return [
            Source(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=(item.get("content") or "")[:1200],
                published_at=item.get("published_date"),
                score=item.get("score"),
            )
            for item in data.get("results", [])
        ]


class FakeSearchProvider(SearchProvider):
    """Tarmoqqa chiqmaydigan namuna — test va dry-run uchun."""

    name = "fake"

    async def search(
        self, query: str, *, max_results: int = 5, recency_days: int | None = None
    ) -> list[Source]:
        return [
            Source(
                title=f"[fake] {query} — natija {i + 1}",
                url=f"https://example.com/{abs(hash(query)) % 9999}/{i + 1}",
                snippet=(
                    f"'{query}' so'rovi bo'yicha namunaviy matn. Haqiqiy provider "
                    f"ulanganda shu yerda maqola mazmuni turadi."
                ),
            )
            for i in range(min(max_results, 3))
        ]


_REGISTRY: dict[str, type[SearchProvider]] = {
    "tavily": TavilySearchProvider,
    "fake": FakeSearchProvider,
}


def get_search_provider(
    name: str | None = None, settings: Settings | None = None
) -> SearchProvider:
    settings = settings or get_settings()
    key = (name or settings.search_provider).lower()
    if key not in _REGISTRY:
        raise ValueError(
            f"Noma'lum search provider: '{key}'. Mavjudlari: {', '.join(_REGISTRY)}"
        )
    return _REGISTRY[key](settings)


def register_search_provider(name: str, cls: type[SearchProvider]) -> None:
    _REGISTRY[name.lower()] = cls
