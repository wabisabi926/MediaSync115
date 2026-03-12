from app.services.app_metadata_service import AppMetadataService
from app.services.update_check_service import UpdateCheckService


def test_app_metadata_uses_build_env(monkeypatch):
    monkeypatch.setenv("APP_BUILD_VERSION", "latest")
    monkeypatch.setenv("APP_BUILD_TAG", "latest")
    monkeypatch.setenv("APP_BUILD_GIT_SHA", "abcdef123456")
    monkeypatch.setenv("APP_BUILD_TIME", "2026-03-12T10:00:00Z")

    service = AppMetadataService()
    payload = service.get_current_metadata()

    assert payload["current_version"] == "latest"
    assert payload["current_image_tag"] == "latest"
    assert payload["current_git_sha"] == "abcdef123456"
    assert payload["current_build_time"] == "2026-03-12T10:00:00Z"
    assert payload["is_docker_build"] is True


def test_normalize_official_repository():
    service = UpdateCheckService()
    assert service.normalize_repository("official", "") == "wangsy1007/mediasync115"


def test_normalize_custom_repository_variants():
    service = UpdateCheckService()
    assert service.normalize_repository("custom_dockerhub", "docker.io/demo/app:latest") == "demo/app"
    assert service.normalize_repository("custom_dockerhub", "https://hub.docker.com/r/demo/app") == "demo/app"


def test_normalize_custom_repository_rejects_invalid():
    service = UpdateCheckService()
    try:
        service.normalize_repository("custom_dockerhub", "invalid")
    except ValueError as exc:
        assert "namespace/name" in str(exc)
    else:
        raise AssertionError("expected ValueError")
