"""
搜索 API 测试
"""
import pytest
from fastapi.testclient import TestClient


class TestSearch:
    """搜索功能测试类"""

    def test_search_without_query(self, client: TestClient) -> None:
        """测试无查询参数的搜索"""
        response = client.get("/api/search")
        assert response.status_code == 422

    def test_search_with_query(self, client: TestClient) -> None:
        """测试正常搜索"""
        response = client.get("/api/search?query=batman")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total_results" in data
        assert isinstance(data["items"], list)

    def test_search_pagination(self, client: TestClient) -> None:
        """测试搜索分页"""
        response = client.get("/api/search?query=batman&page=1")
        assert response.status_code == 200
        data = response.json()
        assert data["page"] == 1

    def test_explore_popular(self, client: TestClient) -> None:
        """测试热门榜单"""
        response = client.get("/api/search/explore/popular")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)

    def test_explore_sections(self, client: TestClient) -> None:
        """测试探索分类"""
        response = client.get("/api/search/explore/sections?source=douban")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
