import logging

logger = logging.getLogger(__name__)


async def tg_bot_notify(text: str, parse_mode: str = "HTML") -> None:
    try:
        from .service import tg_bot_service
        await tg_bot_service.send_notification(text, parse_mode)
    except Exception:
        logger.debug("TG Bot notification failed", exc_info=True)
