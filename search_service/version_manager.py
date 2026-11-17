from __future__ import annotations

import json
import os
import re
import threading
import uuid
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .index_loader import IndexLoader, IndexSnapshot, IndexValidationError


@dataclass(frozen=True)
class VersionInfo:
    name: str
    path: Path
    metadata: dict[str, Any]


class VersionManager:
    def __init__(
        self,
        serving_root: str | Path,
        loader: IndexLoader | None = None,
    ) -> None:
        self.serving_root = Path(serving_root).expanduser().resolve()
        self.loader = loader or IndexLoader(self.serving_root)
        self._active: IndexSnapshot | None = None
        self._history: list[str] = []
        self._lock = threading.RLock()

    @property
    def active(self) -> IndexSnapshot | None:
        with self._lock:
            return self._active

    @property
    def current_path(self) -> Path:
        with self._lock:
            if self._active is not None:
                return self._active.version_path
        current = self.serving_root / "current"
        if current.is_symlink():
            return current.resolve()
        return current

    def _metadata_for(self, path: Path) -> dict[str, Any]:
        metadata_path = path / "metadata.json"
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise IndexValidationError(f"invalid metadata in {path.name}: {exc}") from exc
        if not isinstance(metadata, dict):
            raise IndexValidationError(f"invalid metadata in {path.name}: expected an object")
        created_at = metadata.get("created_at")
        if not isinstance(created_at, str) or not created_at.strip():
            raise IndexValidationError(f"invalid metadata in {path.name}: created_at must be an ISO-8601 timestamp")
        try:
            datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError as exc:
            raise IndexValidationError(
                f"invalid metadata in {path.name}: created_at must be an ISO-8601 timestamp"
            ) from exc
        return metadata

    @staticmethod
    def _version_number(info: VersionInfo) -> int:
        value = info.metadata.get("version")
        if isinstance(value, int) and not isinstance(value, bool):
            return value
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                pass
        numbers = re.findall(r"\d+", info.name)
        return int(numbers[-1]) if numbers else -1

    @classmethod
    def _sort_key(cls, info: VersionInfo) -> tuple[int, datetime, str]:
        created_at = datetime.fromisoformat(str(info.metadata["created_at"]).replace("Z", "+00:00"))
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        else:
            created_at = created_at.astimezone(timezone.utc)
        return cls._version_number(info), created_at, info.name

    def discover_versions(self) -> list[VersionInfo]:
        if not self.serving_root.is_dir():
            return []
        versions: list[VersionInfo] = []
        for path in self.serving_root.iterdir():
            if not path.is_dir() or path.is_symlink() or path.name.startswith("."):
                continue
            if not (path / "metadata.json").is_file():
                continue
            try:
                metadata = self._metadata_for(path)
            except IndexValidationError:
                continue
            versions.append(VersionInfo(name=path.name, path=path.resolve(), metadata=metadata))
        versions.sort(key=self._sort_key)
        return versions

    def available_versions(self) -> list[str]:
        return [version.name for version in self.discover_versions()]

    def validate_version(self, version: str | Path) -> IndexSnapshot:
        path = Path(version)
        if not path.is_absolute():
            path = self.serving_root / path
        path = path.expanduser().resolve()
        try:
            path.relative_to(self.serving_root)
        except ValueError as exc:
            raise IndexValidationError("version must be inside the serving root") from exc
        return self.loader.load(path)

    def validate_versions(self) -> dict[str, str | None]:
        results: dict[str, str | None] = {}
        for version in self.discover_versions():
            try:
                self.loader.load(version.path)
            except Exception as exc:
                results[version.name] = str(exc)
            else:
                results[version.name] = None
        return results

    def _current_target(self) -> Path | None:
        current = self.serving_root / "current"
        if not current.exists() and not current.is_symlink():
            return None
        if not current.is_symlink():
            raise IndexValidationError("current must be a symlink")
        target = current.resolve()
        try:
            target.relative_to(self.serving_root)
        except ValueError as exc:
            raise IndexValidationError("current symlink points outside the serving root") from exc
        return target

    def _atomic_switch(self, target: Path) -> None:
        self.serving_root.mkdir(parents=True, exist_ok=True)
        current = self.serving_root / "current"
        temporary = self.serving_root / f".current-{uuid.uuid4().hex}.tmp"
        relative_target = target.relative_to(self.serving_root)
        try:
            os.symlink(relative_target.as_posix(), temporary)
            os.replace(temporary, current)
        except Exception:
            with suppress(FileNotFoundError):
                temporary.unlink()
            raise

    def _set_active(self, snapshot: IndexSnapshot) -> None:
        with self._lock:
            self._active = snapshot

    def initialize(self) -> IndexSnapshot:
        target = self._current_target()
        if target is not None:
            snapshot = self.loader.load(target)
            self._set_active(snapshot)
            return snapshot
        versions = self.discover_versions()
        if not versions:
            raise IndexValidationError(f"no index versions found in {self.serving_root}")
        errors: list[str] = []
        for version in reversed(versions):
            try:
                snapshot = self.loader.load(version.path)
            except Exception as exc:
                errors.append(f"{version.name}: {exc}")
                continue
            self._atomic_switch(version.path)
            self._set_active(snapshot)
            return snapshot
        raise IndexValidationError("no valid index version could be loaded: " + "; ".join(errors))

    def switch_to(self, version: str | Path) -> IndexSnapshot:
        path = Path(version)
        if not path.is_absolute():
            path = self.serving_root / path
        path = path.expanduser().resolve()
        try:
            path.relative_to(self.serving_root)
        except ValueError as exc:
            raise IndexValidationError("version must be inside the serving root") from exc
        if not path.is_dir():
            raise IndexValidationError(f"version does not exist: {path.name}")
        snapshot = self.loader.load(path)
        current = self._current_target()
        previous_name = current.name if current is not None else None
        self._atomic_switch(path)
        self._set_active(snapshot)
        if previous_name is not None and previous_name != path.name:
            self._history.append(previous_name)
        return snapshot

    def reload_current(self) -> bool:
        target = self._current_target()
        if target is None:
            return False
        with self._lock:
            active = self._active
        if active is not None and active.version_path == target:
            return False
        snapshot = self.loader.load(target)
        self._set_active(snapshot)
        return True

    def rollback(self) -> IndexSnapshot:
        with self._lock:
            target_name = self._history.pop() if self._history else None
        if target_name is None:
            current = self._current_target()
            versions = self.discover_versions()
            current_name = current.name if current is not None else None
            candidates = [version for version in versions if version.name != current_name]
            if current_name is not None:
                assert current is not None
                current_number = self._version_number(
                    VersionInfo(current_name, current, self._metadata_for(current))
                )
                earlier = [version for version in candidates if self._version_number(version) < current_number]
                if earlier:
                    candidates = earlier
            if not candidates:
                raise IndexValidationError("no previous version is available for rollback")
            target_name = max(candidates, key=self._version_number).name
        path = self.serving_root / target_name
        snapshot = self.loader.load(path)
        current = self._current_target()
        previous_name = current.name if current is not None else None
        self._atomic_switch(path)
        self._set_active(snapshot)
        if previous_name is not None and previous_name != target_name:
            self._history.append(previous_name)
        return snapshot

    def close(self) -> None:
        with self._lock:
            self._active = None
