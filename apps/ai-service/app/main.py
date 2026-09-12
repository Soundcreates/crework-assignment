from contextlib import asynccontextmanager
import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import companies, discovery, health
from app.config import get_settings
from app.db.supabase import Database
from app.runtime import should_enable_reload
from app.utils.retry import setup_logging

logger = logging.getLogger(__name__)


async def _reaper_loop(stop: asyncio.Event) -> None:
    settings = get_settings()
    db = Database()
    while not stop.is_set():
        try:
            failed = db.fail_stale_runs(settings.stale_run_minutes)
            if failed:
                logger.warning("stale-run reaper marked %s runs failed", failed)
        except Exception as exc:  # noqa: BLE001
            logger.warning("stale-run reaper error=%s", exc)
        try:
            await asyncio.wait_for(stop.wait(), timeout=60)
        except TimeoutError:
            continue


@asynccontextmanager
async def lifespan(app: FastAPI):
    stop = asyncio.Event()
    task = asyncio.create_task(_reaper_loop(stop))
    try:
        yield
    finally:
        stop.set()
        task.cancel()


def create_app() -> FastAPI:
    setup_logging()
    settings = get_settings()
    origins = {
        settings.frontend_url,
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    }
    app = FastAPI(
        title="Lead Intelligence AI Service",
        version="0.1.0",
        description="Search, crawl, enrich, extract signals, and score buying intent.",
        lifespan=lifespan,
    )
    # Next.js often hops to 3001 when 3000 is taken. Starlette returns 400 on
    # CORS preflight if Origin is not allow-listed — the browser then shows
    # "Failed to fetch" even though uvicorn is healthy.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=sorted(o for o in origins if o),
        allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(discovery.router, prefix="/v1")
    app.include_router(companies.router, prefix="/v1")
    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=should_enable_reload(),
    )
