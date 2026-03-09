import asyncio
import logging
import time
from typing import Any

import httpx

from app.services.douban_explore_service import DOUBAN_SECTION_SOURCES, fetch_douban_section
from app.services.tmdb_explore_service import TMDB_SECTION_SOURCES, fetch_tmdb_section

logger = logging.getLogger("uvicorn.error")

EXPLORE_HOME_WARMUP_LIMIT = 12
EXPLORE_HOME_WARMUP_TIMEOUT_SECONDS = 60.0


class ExploreHomeWarmupService:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    async def warmup(self, force_refresh: bool = False) -> dict[str, Any]:
        async with self._lock:
            started_at = time.perf_counter()
            logger.info("explore home warmup started force_refresh=%s", force_refresh)
            try:
                result = await asyncio.wait_for(
                    self._warmup_all_sources(force_refresh=force_refresh),
                    timeout=EXPLORE_HOME_WARMUP_TIMEOUT_SECONDS,
                )
                result["timed_out"] = False
            except asyncio.TimeoutError:
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                logger.warning(
                    "explore home warmup timed out after %sms",
                    elapsed_ms,
                )
                return {
                    "success": False,
                    "timed_out": True,
                    "elapsed_ms": elapsed_ms,
                    "sources": [],
                    "message": "explore home warmup timed out",
                }
            except Exception as exc:
                elapsed_ms = int((time.perf_counter() - started_at) * 1000)
                logger.warning(
                    "explore home warmup failed after %sms: %s",
                    elapsed_ms,
                    exc,
                )
                return {
                    "success": False,
                    "timed_out": False,
                    "elapsed_ms": elapsed_ms,
                    "sources": [],
                    "message": f"explore home warmup failed: {exc}",
                }

            result["elapsed_ms"] = int((time.perf_counter() - started_at) * 1000)
            result["message"] = "explore home warmup completed"
            return result

    async def _warmup_all_sources(self, force_refresh: bool) -> dict[str, Any]:
        results = []
        for source_name in ("douban", "tmdb"):
            results.append(await self._warmup_source(source_name, force_refresh=force_refresh))

        success = all(bool(item.get("success")) for item in results)
        return {
            "success": success,
            "sources": results,
        }

    async def _warmup_source(self, source_name: str, force_refresh: bool) -> dict[str, Any]:
        source_rows = TMDB_SECTION_SOURCES if source_name == "tmdb" else DOUBAN_SECTION_SOURCES
        started_at = time.perf_counter()

        async with httpx.AsyncClient(timeout=12.0, http2=True) as client:
            if source_name == "tmdb":
                tasks = [
                    fetch_tmdb_section(
                        section,
                        EXPLORE_HOME_WARMUP_LIMIT,
                        force_refresh,
                        start=0,
                        client=client,
                    )
                    for section in source_rows
                ]
            else:
                tasks = [
                    fetch_douban_section(
                        section,
                        EXPLORE_HOME_WARMUP_LIMIT,
                        force_refresh,
                        start=0,
                        client=client,
                        home_prime_limit=0,
                    )
                    for section in source_rows
                ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        success_count = 0
        failures: list[dict[str, str]] = []
        items: list[dict[str, Any]] = []
        for section, result in zip(source_rows, results):
            if isinstance(result, Exception):
                failures.append(
                    {
                        "key": str(section.get("key") or ""),
                        "error": str(result),
                    }
                )
                continue
            if not isinstance(result, dict):
                failures.append(
                    {
                        "key": str(section.get("key") or ""),
                        "error": "invalid section payload",
                    }
                )
                continue
            success_count += 1
            section_items = result.get("items")
            if isinstance(section_items, list):
                items.extend(section_items)

        # Warm emby badge cache together with section caches so the first page load avoids recomputing it.
        try:
            from app.api import search as search_api

            await search_api._build_emby_status_map(items)
        except Exception as exc:
            logger.warning("explore home warmup emby badge cache failed for %s: %s", source_name, exc)

        elapsed_ms = int((time.perf_counter() - started_at) * 1000)
        logger.info(
            "explore home warmup source=%s success=%s sections=%s/%s elapsed_ms=%s failures=%s",
            source_name,
            success_count == len(source_rows),
            success_count,
            len(source_rows),
            elapsed_ms,
            failures,
        )
        return {
            "source": source_name,
            "success": success_count == len(source_rows),
            "sections_total": len(source_rows),
            "sections_warmed": success_count,
            "elapsed_ms": elapsed_ms,
            "failures": failures,
        }


explore_home_warmup_service = ExploreHomeWarmupService()
