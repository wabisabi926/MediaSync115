"""
健康检查 API 测试
"""
import pytest
from fastapi.testclient import TestClient


class TestHealth:
    """健康检查测试类"""

    def test_root_endpoint(self, client: TestClient) -> None:
        """测试根端点"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert data["status"] == "running"

    def test_health_endpoint(self, client: TestClient) -> None:
        """测试健康检查端点"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

    def test_openapi_docs(self, client: TestClient) -> None:
        """测试 API 文档端点"""
        response = client.get("/docs")
        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]

    def test_openapi_json(self, client: TestClient) -> None:
        """测试 OpenAPI JSON 端点"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        data = response.json()
        assert data["openapi"].startswith("3.")
        assert "paths" in data
