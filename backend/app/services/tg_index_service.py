import re
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, or_, select

from app.core.database import async_session_maker
from app.models.models import TgMessageIndex, TgSyncState


class TgIndexService:
    _NOISE_WORDS = {
        "电影",
        "电视剧",
        "剧集",
        "全集",
        "国语",
        "中字",
        "双语",
        "高清",
        "超清",
        "蓝光",
        "4k",
        "1080p",
        "720p",
        "h265",
        "x265",
        "web",
        "webrip",
        "bdrip",
        "dvdrip",
        "remux",
    }

    @staticmethod
    def _normalize_text(value: Any) -> str:
        text = str(value or "").strip().lower()
        if not text:
            return ""
        text = re.sub(r"\s+", " ", text)
        return text

    @staticmethod
    def _normalize_for_match(value: Any) -> str:
        text = str(value or "").strip().lower()
        if not text:
            return ""
        text = re.sub(r"[`~!@#$%^&*()_+=\[\]{}\\|;:'\",.<>/?，。！？：；【】（）《》、·\-]+", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _title_tokens(value: str) -> list[str]:
        normalized = TgIndexService._normalize_for_match(value)
        if not normalized:
            return []
        return [part for part in normalized.split(" ") if part and part not in TgIndexService._NOISE_WORDS and len(part) >= 2]

    @staticmethod
    def _contains_phrase(target: str, phrase: str) -> bool:
        if not target or not phrase:
            return False
        return phrase in target

    @staticmethod
    def _contains_all_tokens(target: str, tokens: list[str]) -> bool:
        if not target or not tokens:
            return False
        return all(token in target for token in tokens)

    @staticmethod
    def _extract_year(value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        matched = re.search(r"(19\d{2}|20\d{2})", text)
        if not matched:
            return ""
        return matched.group(1)

    def _score_row_relevance(
        self,
        *,
        row_title: str,
        row_overview: str,
        expected_title: str,
        expected_original_title: str,
        expected_year: str,
    ) -> tuple[int, str, bool]:
        title_norm = self._normalize_for_match(row_title)
        overview_norm = self._normalize_for_match(row_overview)
        full_text = f"{title_norm} {overview_norm}".strip()

        exp_title_norm = self._normalize_for_match(expected_title)
        exp_original_norm = self._normalize_for_match(expected_original_title)
        title_tokens = self._title_tokens(expected_title)
        original_tokens = self._title_tokens(expected_original_title)

        score = 0
        reasons: list[str] = []
        strong_hit = False

        if exp_title_norm and self._contains_phrase(title_norm, exp_title_norm):
            score += 60
            strong_hit = True
            reasons.append("title_exact")
        elif exp_title_norm and self._contains_phrase(full_text, exp_title_norm):
            score += 45
            strong_hit = True
            reasons.append("title_phrase")

        if exp_original_norm and self._contains_phrase(title_norm, exp_original_norm):
            score += 45
            strong_hit = True
            reasons.append("original_exact")
        elif exp_original_norm and self._contains_phrase(full_text, exp_original_norm):
            score += 30
            strong_hit = True
            reasons.append("original_phrase")

        if title_tokens and self._contains_all_tokens(full_text, title_tokens):
            score += 20
            reasons.append("title_tokens")
        if original_tokens and self._contains_all_tokens(full_text, original_tokens):
            score += 15
            reasons.append("original_tokens")

        normalized_expected_year = self._extract_year(expected_year)
        if normalized_expected_year:
            if normalized_expected_year in full_text:
                score += 20
                reasons.append("year")
            else:
                score -= 40
                reasons.append("year_missing")

        if "合集" in title_norm or "合集" in overview_norm:
            score -= 8
            reasons.append("collection_penalty")

        reason_text = ",".join(reasons) if reasons else "none"
        return score, reason_text, strong_hit

    def _build_search_text(self, row: dict[str, Any]) -> str:
        parts = [
            self._normalize_text(row.get("title") or row.get("resource_name") or ""),
            self._normalize_text(row.get("overview") or ""),
            self._normalize_text(row.get("tg_channel") or ""),
        ]
        return " ".join([part for part in parts if part]).strip()

    async def upsert_rows(self, rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0

        changed = 0
        async with async_session_maker() as db:
            for row in rows:
                channel = str(row.get("tg_channel") or "").strip()
                message_id = int(row.get("tg_message_id") or 0)
                share_link = str(row.get("pan115_share_link") or row.get("share_link") or "").strip()
                if not channel or message_id <= 0 or not share_link:
                    continue

                stmt = select(TgMessageIndex).where(
                    TgMessageIndex.channel_username == channel,
                    TgMessageIndex.message_id == message_id,
                    TgMessageIndex.share_link == share_link,
                ).limit(1)
                result = await db.execute(stmt)
                entity = result.scalar_one_or_none()

                message_date_raw = row.get("tg_message_date")
                message_date = None
                if isinstance(message_date_raw, str) and message_date_raw.strip():
                    try:
                        message_date = datetime.fromisoformat(message_date_raw.strip())
                    except Exception:
                        message_date = None

                resource_name = str(row.get("resource_name") or row.get("title") or "Telegram 资源").strip()[:255]
                overview = str(row.get("overview") or "").strip()
                media_type_hint = str(row.get("tg_media_type_hint") or "unknown").strip().lower() or "unknown"
                search_text = self._build_search_text(row)

                if entity is None:
                    entity = TgMessageIndex(
                        channel_username=channel,
                        message_id=message_id,
                        message_date=message_date,
                        resource_name=resource_name,
                        share_link=share_link,
                        message_text=overview,
                        media_type_hint=media_type_hint,
                        search_text=search_text,
                    )
                    db.add(entity)
                    changed += 1
                else:
                    entity.message_date = message_date or entity.message_date
                    entity.resource_name = resource_name
                    entity.message_text = overview
                    entity.media_type_hint = media_type_hint
                    entity.search_text = search_text
                    changed += 1
            await db.commit()
        return changed

    async def search_resources(
        self,
        *,
        keyword: str,
        media_type: str,
        channels: list[str],
        per_channel_limit: int,
        expected_title: str = "",
        expected_original_title: str = "",
        expected_year: str = "",
    ) -> list[dict[str, Any]]:
        normalized_keyword = self._normalize_text(keyword)
        if not normalized_keyword:
            return []

        safe_channels = [str(item or "").strip() for item in channels if str(item or "").strip()]
        if not safe_channels:
            return []

        terms = [part for part in normalized_keyword.split(" ") if part]
        if not terms:
            return []

        normalized_media = "tv" if str(media_type or "").strip().lower() == "tv" else "movie"
        raw_limit = max(20, int(per_channel_limit or 120))
        sample_limit = max(raw_limit * len(safe_channels) * 3, 200)

        async with async_session_maker() as db:
            stmt = select(TgMessageIndex).where(TgMessageIndex.channel_username.in_(safe_channels))
            if normalized_media == "movie":
                stmt = stmt.where(or_(TgMessageIndex.media_type_hint == "movie", TgMessageIndex.media_type_hint == "unknown"))
            else:
                stmt = stmt.where(or_(TgMessageIndex.media_type_hint == "tv", TgMessageIndex.media_type_hint == "unknown"))

            for term in terms:
                stmt = stmt.where(TgMessageIndex.search_text.ilike(f"%{term}%"))

            stmt = stmt.order_by(TgMessageIndex.message_date.desc(), TgMessageIndex.updated_at.desc()).limit(sample_limit)
            result = await db.execute(stmt)
            records = list(result.scalars().all())

        per_channel_count: dict[str, int] = {}
        scored_rows: list[tuple[int, datetime, dict[str, Any]]] = []
        rows: list[dict[str, Any]] = []
        for record in records:
            channel = str(record.channel_username or "")
            current = per_channel_count.get(channel, 0)
            if current >= raw_limit:
                continue
            row_title = str(record.resource_name or "")
            row_overview = str(record.message_text or "")
            score, reason, strong_hit = self._score_row_relevance(
                row_title=row_title,
                row_overview=row_overview,
                expected_title=expected_title,
                expected_original_title=expected_original_title,
                expected_year=expected_year,
            )
            has_context = bool(self._normalize_for_match(expected_title) or self._normalize_for_match(expected_original_title))
            if has_context:
                if not strong_hit:
                    continue
                if score < 80:
                    continue

            per_channel_count[channel] = current + 1
            row = {
                "id": f"tg-index-{channel.replace('@', '')}-{record.message_id}-{current}",
                "media_type": "resource",
                "title": record.resource_name,
                "name": record.resource_name,
                "resource_name": record.resource_name,
                "overview": row_overview[:300],
                "poster_path": "",
                "source_service": "tg",
                "pan115_share_link": record.share_link,
                "share_link": record.share_link,
                "pan115_savable": True,
                "tg_channel": channel,
                "tg_message_id": int(record.message_id or 0),
                "tg_message_date": record.message_date.isoformat() if record.message_date else "",
                "tg_media_type_hint": str(record.media_type_hint or "unknown"),
                "tg_relevance_score": score,
                "tg_match_reason": reason,
            }
            scored_rows.append((score, record.message_date or datetime.min, row))

        scored_rows.sort(key=lambda item: (item[0], item[1]), reverse=True)
        for _, _, row in scored_rows:
            rows.append(row)
        return rows

    async def get_status(self, channels: list[str]) -> dict[str, Any]:
        safe_channels = [str(item or "").strip() for item in channels if str(item or "").strip()]
        async with async_session_maker() as db:
            total_result = await db.execute(select(func.count()).select_from(TgMessageIndex))
            total_messages = int(total_result.scalar_one() or 0)

            channel_counts_result = await db.execute(
                select(TgMessageIndex.channel_username, func.count(TgMessageIndex.id))
                .group_by(TgMessageIndex.channel_username)
                .order_by(TgMessageIndex.channel_username.asc())
            )
            channel_counts = {str(row[0]): int(row[1]) for row in channel_counts_result.all()}

            state_result = await db.execute(select(TgSyncState).order_by(TgSyncState.channel_username.asc()))
            state_rows = list(state_result.scalars().all())
            state_map = {str(row.channel_username): row for row in state_rows}

            ordered_channels: list[str] = []
            for channel in safe_channels:
                if channel not in ordered_channels:
                    ordered_channels.append(channel)
            for channel in channel_counts.keys():
                if channel not in ordered_channels:
                    ordered_channels.append(channel)

            channels_status: list[dict[str, Any]] = []
            for channel in ordered_channels:
                state = state_map.get(channel)
                channels_status.append(
                    {
                        "channel": channel,
                        "indexed_count": int(channel_counts.get(channel, 0)),
                        "last_message_id": int(state.last_message_id or 0) if state else 0,
                        "last_message_date": state.last_message_date.isoformat() if state and state.last_message_date else "",
                        "last_synced_at": state.last_synced_at.isoformat() if state and state.last_synced_at else "",
                        "backfill_completed": bool(state.backfill_completed) if state else False,
                        "last_error": str(state.last_error or "") if state else "",
                    }
                )

        return {
            "total_indexed": total_messages,
            "channels": channels_status,
        }

    async def clear_all(self) -> None:
        async with async_session_maker() as db:
            await db.execute(delete(TgMessageIndex))
            await db.execute(delete(TgSyncState))
            await db.commit()


tg_index_service = TgIndexService()
