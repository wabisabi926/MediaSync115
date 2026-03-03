from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Any

from app.services.emby_service import emby_service
from app.services.tmdb_service import tmdb_service


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

        emby_result = await emby_service.get_downloaded_episodes_with_status(normalized_tmdb_id)
        if emby_result.get("status") != "ok":
            result = {
                "status": str(emby_result.get("status") or "emby_error"),
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
            for pair in (emby_result.get("episodes") or [])
            if isinstance(pair, (list, tuple)) and len(pair) == 2
        }
        if not include_specials:
            existing_pairs_all = {pair for pair in existing_pairs_all if pair[0] > 0}

        try:
            aired_pairs = await self._collect_aired_episodes(normalized_tmdb_id, include_specials=include_specials)
        except Exception as exc:
            result = {
                "status": "tmdb_error",
                "message": f"TMDB 查询失败: {str(exc)}",
                "aired_episodes": [],
                "existing_episodes": self._sorted_pairs(existing_pairs_all),
                "missing_episodes": [],
                "missing_by_season": {},
                "counts": {"aired": 0, "existing": len(existing_pairs_all), "missing": 0},
            }
            await self._set_cached_status(cache_key, result)
            return result

        # “已入库集数”只统计已播出范围内，避免未播出/特别篇干扰统计。
        existing_pairs = existing_pairs_all & aired_pairs
        missing_pairs = aired_pairs - existing_pairs

        result = {
            "status": "ok",
            "message": "缺集状态计算完成",
            "aired_episodes": self._sorted_pairs(aired_pairs),
            "existing_episodes": self._sorted_pairs(existing_pairs),
            "missing_episodes": self._sorted_pairs(missing_pairs),
            "missing_by_season": self._to_season_map(missing_pairs),
            "counts": {
                "aired": len(aired_pairs),
                "existing": len(existing_pairs),
                "missing": len(missing_pairs),
            },
        }
        await self._set_cached_status(cache_key, result)
        return result

    async def _collect_aired_episodes(self, tmdb_id: int, include_specials: bool = False) -> set[tuple[int, int]]:
        detail = await tmdb_service.get_tv_detail(tmdb_id)
        seasons = detail.get("seasons") if isinstance(detail, dict) else []
        if not isinstance(seasons, list):
            seasons = []

        today = date.today()
        season_numbers: list[int] = []
        for season in seasons:
            if not isinstance(season, dict):
                continue
            season_number = self._to_positive_int(season.get("season_number"))
            if season_number is None:
                continue
            if season_number == 0 and not include_specials:
                continue

            season_air_date = self._parse_iso_date(str(season.get("air_date") or ""))
            if season_air_date and season_air_date > today:
                continue
            season_numbers.append(season_number)

        semaphore = asyncio.Semaphore(4)

        async def fetch_one_season(season_number: int) -> list[dict[str, Any]]:
            async with semaphore:
                season_detail = await tmdb_service.get_tv_season_detail(tmdb_id, season_number)
                episodes = season_detail.get("episodes") if isinstance(season_detail, dict) else []
                return episodes if isinstance(episodes, list) else []

        season_episode_lists = await asyncio.gather(
            *(fetch_one_season(season_number) for season_number in season_numbers),
            return_exceptions=True,
        )

        aired_pairs: set[tuple[int, int]] = set()
        for season_number, episodes_or_error in zip(season_numbers, season_episode_lists):
            if isinstance(episodes_or_error, Exception):
                continue
            for episode in episodes_or_error:
                if not isinstance(episode, dict):
                    continue
                episode_number = self._to_positive_int(episode.get("episode_number"))
                if episode_number is None:
                    continue
                air_date = self._parse_iso_date(str(episode.get("air_date") or ""))
                if air_date and air_date > today:
                    continue
                aired_pairs.add((season_number, episode_number))
        return aired_pairs

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
    def _parse_iso_date(value: str) -> date | None:
        text = str(value or "").strip()
        if not text:
            return None
        try:
            return datetime.strptime(text, "%Y-%m-%d").date()
        except Exception:
            return None

    @staticmethod
    def _to_positive_int(value: Any) -> int | None:
        try:
            number = int(value)
        except Exception:
            return None
        if number < 0:
            return None
        return number

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
