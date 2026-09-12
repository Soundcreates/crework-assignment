from typing import Protocol

from app.ai.schemas import SearchResult


class SearchProvider(Protocol):
    async def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        ...
