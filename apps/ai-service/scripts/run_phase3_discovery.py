#!/usr/bin/env python3
"""Run search discovery locally.

Usage:
  cd apps/ai-service
  source .venv/bin/activate
  PYTHONPATH=. python scripts/run_phase3_discovery.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.workflows.search_discovery import SearchDiscoveryService


async def main() -> None:
    get_settings.cache_clear()
    settings = get_settings()
    service = SearchDiscoveryService()
    run_id = str(uuid4())
    result = await service.run(
        run_id=run_id,
        industries=["SaaS", "AI", "Developer Tools"],
        max_companies=10,
        persist=True,
        discovery_only=True,
    )
    payload = {
        "run_id": result.run_id,
        "status": result.status,
        "provider": result.search_provider,
        "search_provider_setting": settings.search_provider,
        "supabase_configured": bool(settings.supabase_url and settings.supabase_service_role_key),
        "queries_generated": len(result.queries),
        "search_results_found": len(result.search_results),
        "companies_discovered": len(result.companies),
        "companies_saved": len(result.saved_companies),
        "companies": [
            {
                "name": c.company_name,
                "domain": c.company_domain,
                "confidence": c.confidence,
                "source_url": c.source_url,
            }
            for c in result.companies
        ],
        "error": result.error,
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
