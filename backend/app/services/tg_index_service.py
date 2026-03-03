import re
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, or_, select

from app.core.database import async_session_maker
from app.models.models import TgMessageIndex, TgSyncState


class TgIndexService:
    @staticmethod
    def _normalize_text(value: Any) -> str:
        text = str(value or "").strip().lower()
        if not text:
            return ""
        text = re.sub(r"\s+", " ", text)
        return text

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
        rows: list[dict[str, Any]] = []
        for record in records:
            channel = str(record.channel_username or "")
            current = per_channel_count.get(channel, 0)
            if current >= raw_limit:
                continue
            per_channel_count[channel] = current + 1
            rows.append(
                {
                    "id": f"tg-index-{channel.replace('@', '')}-{record.message_id}-{current}",
                    "media_type": "resource",
                    "title": record.resource_name,
                    "name": record.resource_name,
                    "resource_name": record.resource_name,
                    "overview": str(record.message_text or "")[:300],
                    "poster_path": "",
                    "source_service": "tg",
                    "pan115_share_link": record.share_link,
                    "share_link": record.share_link,
                    "pan115_savable": True,
                    "tg_channel": channel,
                    "tg_message_id": int(record.message_id or 0),
                    "tg_message_date": record.message_date.isoformat() if record.message_date else "",
                    "tg_media_type_hint": str(record.media_type_hint or "unknown"),
                }
            )
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
