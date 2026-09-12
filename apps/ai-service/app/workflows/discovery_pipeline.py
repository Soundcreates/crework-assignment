from __future__ import annotations

from app.db.supabase import Database
from app.workflows.discovery_graph import run_discovery_graph


class DiscoveryPipeline:
    """Facade over the LangGraph discovery workflow."""

    def __init__(self, db: Database | None = None):
        self.db = db or Database()

    async def run(
        self,
        run_id: str,
        industries: list[str] | None = None,
        country: str | None = None,
        max_companies: int = 25,
        *,
        discovery_only: bool = False,
        keywords: list[str] | None = None,
        icp: dict | None = None,
    ) -> None:
        await run_discovery_graph(
            run_id=run_id,
            industries=industries,
            keywords=keywords,
            country=country,
            max_companies=max_companies,
            discovery_only=discovery_only,
            persist=True,
            db=self.db,
            icp=icp,
        )
