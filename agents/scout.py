from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from pathlib import Path

from mocks.fixtures import mock_issues
from schemas.models import Issue

log = logging.getLogger("scout")
_MEM_CACHE: dict[str, list[Issue]] = {}
_discover_calls = 0


def _cache_dir() -> Path:
    override = os.environ.get("CAMPAIGN_COPILOT_SCOUT_CACHE")
    if override:
        return Path(override)
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg_cache) if xdg_cache else Path.home() / ".cache"
    return base / "campaign-copilot" / "scout"


def _normalize_region(region: str) -> str:
    return re.sub(r"\s+", " ", region.strip().lower())


def _cache_key(region: str) -> str:
    return hashlib.sha256(_normalize_region(region).encode()).hexdigest()[:16]


def _read_disk(key: str, norm_region: str) -> list[Issue] | None:
    path = _cache_dir() / f"{key}.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            return None
        stored = payload.get("region")
        if not isinstance(stored, str) or _normalize_region(stored) != norm_region:
            return None
        return [Issue.model_validate(d) for d in payload["issues"]]
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        log.debug("scout disk cache corrupt or invalid key=%s", key)
        return None


def _write_disk(key: str, norm_region: str, issues: list[Issue]) -> None:
    try:
        cache_dir = _cache_dir()
        cache_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "region": norm_region,
            "issues": [i.model_dump(mode="json") for i in issues],
        }
        path = cache_dir / f"{key}.json"
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError:
        log.debug("scout disk cache write failed key=%s", key, exc_info=True)


def _discover_issues(region: str) -> list[Issue]:
    """Mocked cluster for now. Real path (WS-1 owner replaces this body):
        articles = fetch_news(region)        # tools/news.py   (1.1)
        posts    = load_social(region)       # tools/social.py (1.2)
        return cluster(articles + posts)     # agents/scout.py::cluster (1.3)
    """
    global _discover_calls
    _discover_calls += 1
    return mock_issues()


def run(region: str, *, refresh: bool = False) -> list[Issue]:
    norm_region = _normalize_region(region)
    key = _cache_key(region)
    if not refresh:
        if key in _MEM_CACHE:
            log.debug("scout cache hit (mem) region=%s", region)
            return [i.model_copy(deep=True) for i in _MEM_CACHE[key]]
        disk = _read_disk(key, norm_region)
        if disk is not None:
            log.debug("scout cache hit (disk) region=%s", region)
            _MEM_CACHE[key] = disk
            return [i.model_copy(deep=True) for i in disk]
    issues = _discover_issues(region)
    ranked = sorted(issues, key=lambda i: i.salience, reverse=True)
    _MEM_CACHE[key] = ranked
    _write_disk(key, norm_region, ranked)
    log.debug("scout cache miss region=%s -> %d issues", region, len(ranked))
    return [i.model_copy(deep=True) for i in ranked]


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    region = "Florida HD-21"
    _MEM_CACHE.clear()
    first = run(region, refresh=True)
    assert first and all(isinstance(i, Issue) for i in first)
    assert first == sorted(first, key=lambda i: i.salience, reverse=True), "not ranked"
    assert _discover_calls == 1
    second = run(region)
    assert _discover_calls == 1, "2nd call recomputed"
    _MEM_CACHE.clear()
    third = run(region)
    assert _discover_calls == 1, "disk cache missed"
    assert [i.id for i in third] == [i.id for i in first]
    fourth = run("  florida   hd-21  ")
    assert _discover_calls == 1, "equivalent region recomputed"
    print(f"OK: {len(first)} ranked issues; discover ran once across 4 calls")
