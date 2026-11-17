from __future__ import annotations

import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from search_service.main import create_app
from search_service.version_manager import VersionManager


def test_search_api_returns_documented_contract(index_directory: Path, tmp_path: Path) -> None:
    serving_root = tmp_path / "serving"
    serving_root.mkdir()
    local_version = serving_root / "index-v0"
    shutil.copytree(index_directory, local_version)
    manager = VersionManager(serving_root)
    manager.switch_to(local_version)
    app = create_app(version_manager=manager)
    with TestClient(app) as client:
        response = client.get("/search", params={"q": "april"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["query"] == "april"
        assert payload["total"] == 1
        assert payload["latency_ms"] >= 0
        assert payload["index_version"] == "0"
        result = payload["results"][0]
        assert result["document_id"] == "1"
        assert result["bm25_score"] > 0
        assert result["pagerank_score"] > 0
        assert 0 <= result["final_score"] <= 1
        assert "Matched" in result["explanation"]


def test_document_endpoint_returns_document(index_directory: Path, tmp_path: Path) -> None:
    serving_root = tmp_path / "serving"
    serving_root.mkdir()
    local_version = serving_root / "index-v0"
    shutil.copytree(index_directory, local_version)
    manager = VersionManager(serving_root)
    manager.switch_to(local_version)
    with TestClient(create_app(version_manager=manager)) as client:
        response = client.get("/documents/1")
        assert response.status_code == 200
        assert response.json()["document_id"] == "1"
        assert response.json()["text"] == "April is a month"


def test_api_token_is_enforced_when_configured(
    index_directory: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    serving_root = tmp_path / "serving"
    serving_root.mkdir()
    local_version = serving_root / "index-v0"
    shutil.copytree(index_directory, local_version)
    manager = VersionManager(serving_root)
    manager.switch_to(local_version)
    monkeypatch.setenv("SEARCH_API_TOKEN", "secret-token")
    with TestClient(create_app(version_manager=manager)) as client:
        assert client.get("/health").status_code == 401
        authorized = client.get("/health", headers={"Authorization": "Bearer secret-token"})
        assert authorized.status_code == 200


def test_unknown_document_returns_structured_404(index_directory: Path, tmp_path: Path) -> None:
    serving_root = tmp_path / "serving"
    serving_root.mkdir()
    local_version = serving_root / "index-v0"
    shutil.copytree(index_directory, local_version)
    manager = VersionManager(serving_root)
    manager.switch_to(local_version)
    with TestClient(create_app(version_manager=manager)) as client:
        response = client.get("/documents/missing")
        assert response.status_code == 404
        assert response.json()["error"]["code"] == "not_found"
