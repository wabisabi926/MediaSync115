from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Any

from app.services.emby_service import emby_service


class TvMissingService:
    def __init__(self) -> None:
        self._cache_ttl_seconds = 300
        self._status_cache: dict[str, dict[str, Any]] = {}
        self._cache_lock = asyncio.Lock()

    async def get_tv_missing_status(
        self,
        tmdb_id: int,
        include_specials: bool = False,
        refresh: bool = False,
    ) -> dict[str, Any]:
        normalized_tmdb_id = int(tmdb_id or 0)
        if normalized_tmdb_id <= 0:
            return {
                "status": "invalid_tmdb",
                "message": "无效的 TMDB ID",
                "aired_episodes": [],
                "existing_episodes": [],
                "missing_episodes": [],
                "missing_by_season": {},
                "counts": {"aired": 0, "existing": 0, "missing": 0},
            }

        cache_key = f"{normalized_tmdb_id}:{1 if include_specials else 0}"
        if not refresh:
            cached = await self._get_cached_status(cache_key)
            if cached is not None:
                return cached

        emby_result = await emby_service.get_tv_episode_status_by_tmdb(normalized_tmdb_id)
        status_text = str(emby_result.get("status") or "")
        if status_text not in {"ok", "partial"}:
            result = {
                "status": status_text or "emby_error",
                "message": str(emby_result.get("message") or "Emby 查询失败"),
                "aired_episodes": [],
                "existing_episodes": [],
                "missing_episodes": [],
                "missing_by_season": {},
                "counts": {"aired": 0, "existing": 0, "missing": 0},
            }
            await self._set_cached_status(cache_key, result)
            return result

        existing_pairs_all = {
            (int(pair[0]), int(pair[1]))
            for pair in (emby_result.get("existing_episodes") or [])
            if isinstance(pair, (list, tuple)) and len(pair) == 2
        }
        missing_pairs_all = {
            (int(pair[0]), int(pair[1]))
            for pair in (emby_result.get("missing_episodes") or [])
            if isinstance(pair, (list, tuple)) and len(pair) == 2
        }
        if not include_specials:
            existing_pairs_all = {pair for pair in existing_pairs_all if pair[0] > 0}
            missing_pairs_all = {pair for pair in missing_pairs_all if pair[0] > 0}
        aired_pairs = existing_pairs_all | missing_pairs_all

        result = {
            "status": status_text,
            "message": str(emby_result.get("message") or "缺集状态计算完成"),
            "aired_episodes": self._sorted_pairs(aired_pairs),
            "existing_episodes": self._sorted_pairs(existing_pairs_all),
            "missing_episodes": self._sorted_pairs(missing_pairs_all),
            "missing_by_season": self._to_season_map(missing_pairs_all),
            "counts": {
                "aired": len(aired_pairs),
                "existing": len(existing_pairs_all),
                "missing": len(missing_pairs_all),
            },
        }
        await self._set_cached_status(cache_key, result)
        return result

    async def _get_cached_status(self, key: str) -> dict[str, Any] | None:
        now_ts = datetime.utcnow().timestamp()
        async with self._cache_lock:
            cached = self._status_cache.get(key)
            if not cached:
                return None
            ts = float(cached.get("ts") or 0)
            if now_ts - ts > self._cache_ttl_seconds:
                self._status_cache.pop(key, None)
                return None
            payload = cached.get("payload")
            return dict(payload) if isinstance(payload, dict) else None

    async def _set_cached_status(self, key: str, payload: dict[str, Any]) -> None:
        async with self._cache_lock:
            self._status_cache[key] = {
                "ts": datetime.utcnow().timestamp(),
                "payload": dict(payload),
            }
            if len(self._status_cache) > 500:
                oldest_key = min(self._status_cache.items(), key=lambda item: float(item[1].get("ts") or 0))[0]
                self._status_cache.pop(oldest_key, None)

    @staticmethod
    def _sorted_pairs(pairs: set[tuple[int, int]]) -> list[tuple[int, int]]:
        return sorted(pairs, key=lambda item: (item[0], item[1]))

    @staticmethod
    def _to_season_map(pairs: set[tuple[int, int]]) -> dict[str, list[int]]:
        output: dict[str, list[int]] = {}
        for season, episode in sorted(pairs, key=lambda item: (item[0], item[1])):
            key = str(season)
            output.setdefault(key, [])
            output[key].append(episode)
        return output


tv_missing_service = TvMissingService()
