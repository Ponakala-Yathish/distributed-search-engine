from __future__ import annotations

import json
import shutil
from pathlib import Path

from search_service.version_manager import VersionManager


def _copy_version(source: Path, root: Path, name: str, version: int, created_at: str) -> Path:
    target = root / name
    shutil.copytree(source, target)
    metadata_path = target / "metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["version"] = version
    metadata["created_at"] = created_at
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")
    return target


def test_version_discovery_uses_numeric_version_before_timestamp(index_directory: Path, tmp_path) -> None:
    root = tmp_path / "versions"
    root.mkdir()
    _copy_version(index_directory, root, "index-v0", 0, "2026-01-03T00:00:00+00:00")
    _copy_version(index_directory, root, "index-v9", 9, "2026-01-02T00:00:00+00:00")
    _copy_version(index_directory, root, "index-v10", 10, "2026-01-01T00:00:00+00:00")
    manager = VersionManager(root)
    assert manager.available_versions() == ["index-v0", "index-v9", "index-v10"]


def test_rollback_selects_immediately_preceding_numeric_version(index_directory: Path, tmp_path) -> None:
    root = tmp_path / "versions"
    root.mkdir()
    _copy_version(index_directory, root, "index-v9", 9, "2026-01-02T00:00:00+00:00")
    _copy_version(index_directory, root, "index-v10", 10, "2026-01-03T00:00:00+00:00")
    manager = VersionManager(root)
    manager.switch_to("index-v10")
    rolled_back = manager.rollback()
    assert rolled_back.version == "9"


def test_version_with_invalid_timestamp_is_ignored(index_directory: Path, tmp_path) -> None:
    root = tmp_path / "versions"
    root.mkdir()
    invalid = _copy_version(index_directory, root, "index-v0", 0, "not-a-timestamp")
    assert invalid.is_dir()
    manager = VersionManager(root)
    assert manager.available_versions() == []
