import os
from datetime import datetime
from typing import Any

from app.core.config import settings


class AppMetadataService:
    OFFICIAL_UPDATE_REPOSITORY = "wangsy1007/mediasync115"

    @staticmethod
    def _clean(value: object) -> str:
        return str(value or "").strip()

    @staticmethod
    def _normalize_version(value: str) -> str:
        cleaned = str(value or "").strip()
        if cleaned.lower().startswith("v") and len(cleaned) > 1 and cleaned[1].isdigit():
            return cleaned[1:]
        return cleaned

    @staticmethod
    def _normalize_build_time(value: str) -> str:
        cleaned = str(value or "").strip()
        if not cleaned:
            return ""
        try:
            datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
            return cleaned
        except Exception:
            return ""

    def get_current_metadata(self) -> dict[str, Any]:
        build_version = self._normalize_version(os.getenv("APP_BUILD_VERSION", ""))
        image_tag = self._clean(os.getenv("APP_BUILD_TAG", ""))
        git_sha = self._clean(os.getenv("APP_BUILD_GIT_SHA", ""))
        build_time = self._normalize_build_time(os.getenv("APP_BUILD_TIME", ""))

        current_version = build_version or image_tag or self._normalize_version(settings.APP_VERSION)
        if not current_version:
            current_version = "unknown"

        return {
            "app_name": settings.APP_NAME,
            "current_version": current_version,
            "current_image_tag": image_tag or "",
            "current_git_sha": git_sha or "",
            "current_build_time": build_time or "",
            "is_docker_build": bool(image_tag or build_time or git_sha),
        }


app_metadata_service = AppMetadataService()
