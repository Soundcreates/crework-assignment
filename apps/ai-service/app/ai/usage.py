from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass

_run_id: ContextVar[str | None] = ContextVar("ai_usage_run_id", default=None)


@dataclass
class UsageCounters:
    llm_calls: int = 0
    llm_tokens: int = 0
    search_requests: int = 0
    crawl_requests: int = 0


_by_run: dict[str, UsageCounters] = {}


def bind_run(run_id: str | None) -> None:
    _run_id.set(run_id)
    if run_id and run_id not in _by_run:
        _by_run[run_id] = UsageCounters()


def current_run_id() -> str | None:
    return _run_id.get()


def incr(kind: str, amount: int = 1) -> None:
    run_id = _run_id.get()
    if not run_id:
        return
    counters = _by_run.setdefault(run_id, UsageCounters())
    if kind == "llm_calls":
        counters.llm_calls += amount
    elif kind == "llm_tokens":
        counters.llm_tokens += amount
    elif kind == "search_requests":
        counters.search_requests += amount
    elif kind == "crawl_requests":
        counters.crawl_requests += amount


def snapshot(run_id: str | None = None) -> UsageCounters:
    rid = run_id or _run_id.get()
    if not rid:
        return UsageCounters()
    return _by_run.get(rid, UsageCounters())
