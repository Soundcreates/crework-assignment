from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

from supabase import Client, create_client

from app.config import get_settings

logger = logging.getLogger(__name__)

_UNSET = object()


@lru_cache
def get_supabase() -> Client | None:
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        return None
    return create_client(settings.supabase_url, settings.supabase_service_role_key)


class Database:
    def __init__(self, client: Any = _UNSET, *, offline: bool = False):
        if offline or client is None:
            self.client = None
        elif client is _UNSET:
            self.client = get_supabase()
        else:
            self.client = client

    @classmethod
    def offline(cls) -> "Database":
        return cls(offline=True)

    @property
    def available(self) -> bool:
        return self.client is not None

    def update_run(self, run_id: str, **fields: Any) -> None:
        if not self.client:
            return
        try:
            self.client.table("discovery_runs").update(fields).eq("id", run_id).execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("update_run failed run_id=%s error=%s", run_id, exc)

    def upsert_company(self, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not self.client:
            return None
        try:
            if payload.get("normalized_domain"):
                result = (
                    self.client.table("companies")
                    .upsert(payload, on_conflict="normalized_domain")
                    .execute()
                )
            else:
                result = self.client.table("companies").insert(payload).execute()
            row = result.data[0] if result.data else None
            if row is None:
                logger.warning(
                    "upsert_company returned empty data domain=%s",
                    payload.get("normalized_domain"),
                )
            return row
        except Exception as exc:  # noqa: BLE001
            logger.warning("upsert_company failed domain=%s error=%s", payload.get("normalized_domain"), exc)
            optional = {"discovery_run_id", "source", "last_checked_at"}
            if optional & set(payload):
                slim = {k: v for k, v in payload.items() if k not in optional}
                try:
                    if slim.get("normalized_domain"):
                        result = (
                            self.client.table("companies")
                            .upsert(slim, on_conflict="normalized_domain")
                            .execute()
                        )
                    else:
                        result = self.client.table("companies").insert(slim).execute()
                    logger.warning(
                        "upsert_company succeeded after dropping optional columns domain=%s",
                        payload.get("normalized_domain"),
                    )
                    return result.data[0] if result.data else None
                except Exception as retry_exc:  # noqa: BLE001
                    logger.warning(
                        "upsert_company retry failed domain=%s error=%s",
                        payload.get("normalized_domain"),
                        retry_exc,
                    )
            return None

    def replace_signals(self, company_id: str, signals: list[dict[str, Any]]) -> None:
        if not self.client:
            return
        try:
            self.client.table("signals").delete().eq("company_id", company_id).execute()
            if signals:
                for signal in signals:
                    signal["company_id"] = company_id
                self.client.table("signals").insert(signals).execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("replace_signals failed company_id=%s error=%s", company_id, exc)

    def get_company(self, company_id: str) -> dict[str, Any] | None:
        if not self.client:
            return None
        result = self.client.table("companies").select("*").eq("id", company_id).limit(1).execute()
        return result.data[0] if result.data else None

    def get_signals(self, company_id: str) -> list[dict[str, Any]]:
        if not self.client:
            return []
        result = self.client.table("signals").select("*").eq("company_id", company_id).execute()
        return result.data or []

    def replace_contacts(self, company_id: str, contacts: list[dict[str, Any]]) -> None:
        if not self.client:
            return
        try:
            self.client.table("contacts").delete().eq("company_id", company_id).execute()
            if contacts:
                for contact in contacts:
                    contact["company_id"] = company_id
                self.client.table("contacts").insert(contacts).execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("replace_contacts failed company_id=%s error=%s", company_id, exc)

    def get_contacts(self, company_id: str) -> list[dict[str, Any]]:
        if not self.client:
            return []
        try:
            result = (
                self.client.table("contacts").select("*").eq("company_id", company_id).execute()
            )
            return result.data or []
        except Exception:  # noqa: BLE001
            return []

    def get_run(self, run_id: str) -> dict[str, Any] | None:
        if not self.client:
            return None
        try:
            result = (
                self.client.table("discovery_runs")
                .select("*")
                .eq("id", run_id)
                .limit(1)
                .execute()
            )
            return result.data[0] if result.data else None
        except Exception:  # noqa: BLE001
            return None

    def list_recent_companies(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.client:
            return []
        try:
            result = (
                self.client.table("companies")
                .select("*")
                .order("last_updated_at", desc=True)
                .limit(limit)
                .execute()
            )
            return result.data or []
        except Exception:  # noqa: BLE001
            return []

    def list_companies_for_run(self, run_id: str, limit: int = 50) -> list[dict[str, Any]]:
        if not self.client:
            return []
        try:
            result = (
                self.client.table("companies")
                .select("*")
                .eq("discovery_run_id", run_id)
                .order("intent_score", desc=True)
                .limit(limit)
                .execute()
            )
            return result.data or []
        except Exception:  # noqa: BLE001
            return []

    def list_unscored_companies(self, limit: int = 50) -> list[dict[str, Any]]:
        if not self.client:
            return []
        try:
            result = (
                self.client.table("companies")
                .select("*")
                .eq("intent_score", 0)
                .limit(limit)
                .execute()
            )
            return result.data or []
        except Exception:  # noqa: BLE001
            return []

    def list_stale_companies(self, hours: int = 24, limit: int = 25) -> list[dict[str, Any]]:
        if not self.client:
            return []
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        try:
            result = (
                self.client.table("companies")
                .select("*")
                .in_("intent_level", ["HIGH", "MEDIUM HIGH", "MEDIUM"])
                .or_(f"last_checked_at.is.null,last_checked_at.lt.{cutoff}")
                .limit(limit)
                .execute()
            )
            return result.data or []
        except Exception:  # noqa: BLE001
            return []

    def fail_stale_runs(self, minutes: int = 15) -> int:
        if not self.client:
            return 0
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).isoformat()
        try:
            result = (
                self.client.table("discovery_runs")
                .update(
                    {
                        "status": "failed",
                        "error": f"Run timed out after {minutes} minutes (stale-run reaper).",
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                .in_("status", ["pending", "searching", "enriching", "scoring"])
                .lt("started_at", cutoff)
                .execute()
            )
            return len(result.data or [])
        except Exception as exc:  # noqa: BLE001
            logger.warning("fail_stale_runs failed error=%s", exc)
            return 0

    def upsert_run_costs(
        self,
        run_id: str,
        *,
        llm_calls: int = 0,
        llm_tokens: int = 0,
        search_requests: int = 0,
        crawl_requests: int = 0,
    ) -> None:
        if not self.client:
            return
        try:
            self.client.table("discovery_run_costs").insert(
                {
                    "run_id": run_id,
                    "llm_calls": llm_calls,
                    "llm_tokens": llm_tokens,
                    "search_requests": search_requests,
                    "crawl_requests": crawl_requests,
                }
            ).execute()
        except Exception as exc:  # noqa: BLE001
            logger.warning("upsert_run_costs failed run_id=%s error=%s", run_id, exc)

    def get_run_costs(self, run_id: str) -> dict[str, Any] | None:
        if not self.client:
            return None
        try:
            result = (
                self.client.table("discovery_run_costs")
                .select("*")
                .eq("run_id", run_id)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            return result.data[0] if result.data else None
        except Exception:  # noqa: BLE001
            return None
