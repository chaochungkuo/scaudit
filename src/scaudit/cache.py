from __future__ import annotations

import json
import os
import shutil
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CachedResource:
    provider_id: str
    name: str
    url: str
    relative_path: str


def default_cache_root() -> Path:
    env_value = os.environ.get("SCAUDIT_CACHE_DIR", "").strip()
    if env_value:
        return Path(env_value).expanduser()
    return Path("~/.cache/scaudit").expanduser()


def cache_root_from_config(config: dict[str, Any]) -> Path:
    cache = config.get("cache", {})
    if isinstance(cache, dict):
        configured = str(cache.get("dir", "") or "").strip()
        if configured:
            return Path(configured).expanduser()
    return default_cache_root()


def ensure_cached_resource(resource: CachedResource, cache_root: Path, warnings: list[str]) -> Path | None:
    path = (cache_root / resource.relative_path).expanduser()
    if path.exists() and path.stat().st_size > 0:
        return path

    if not resource.url:
        warnings.append(f"No download URL is configured for {resource.name}.")
        return None

    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        try:
            urllib.request.urlretrieve(resource.url, tmp_path)
        except Exception:
            _download_with_user_agent(resource.url, tmp_path)
        if not tmp_path.exists() or tmp_path.stat().st_size == 0:
            warnings.append(f"Downloaded {resource.name} from {resource.url}, but the file was empty.")
            tmp_path.unlink(missing_ok=True)
            return None
        if not _looks_like_data_file(tmp_path):
            warnings.append(f"Downloaded {resource.name} from {resource.url}, but the file did not look like a marker database.")
            tmp_path.unlink(missing_ok=True)
            return None
        tmp_path.replace(path)
        _write_metadata(path, resource)
        return path
    except Exception as exc:
        tmp_path.unlink(missing_ok=True)
        warnings.append(f"Could not download {resource.name} from {resource.url}: {exc}")
        return None


def _download_with_user_agent(url: str, path: Path) -> None:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 scaudit/0.1 (+https://github.com/chaochungkuo/scaudit)",
            "Accept": "text/tab-separated-values,text/plain,application/octet-stream,*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=60) as response, path.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def _write_metadata(path: Path, resource: CachedResource) -> None:
    metadata_path = path.with_suffix(path.suffix + ".metadata.json")
    payload = {
        "provider_id": resource.provider_id,
        "name": resource.name,
        "url": resource.url,
        "local_path": str(path),
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "size_bytes": path.stat().st_size,
    }
    metadata_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _looks_like_data_file(path: Path) -> bool:
    suffix = path.suffix.lower()
    if suffix == ".xlsx":
        return zipfile.is_zipfile(path)
    with path.open("rb") as handle:
        prefix = handle.read(512).lstrip().lower()
    return not (prefix.startswith(b"<!doctype html") or prefix.startswith(b"<html"))
