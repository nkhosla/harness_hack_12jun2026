from __future__ import annotations

import hashlib
import json
import re
import sys
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from importlib import resources
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if __name__ == "__main__" and __package__ is None:
    sys.path.insert(0, str(_REPO_ROOT))

import feedparser  # noqa: E402
import httpx  # noqa: E402

from schemas.models import Article  # noqa: E402

_DEFAULT_REGION = "NC HD-50"
_CACHE_DIR = _REPO_ROOT / "data/cache/news"
_SEED_FIXTURE = "resources/news.sample.json"
_FETCH_TIMEOUT = 15.0

REGION_FEEDS: dict[str, list[str]] = {
    "NC HD-50": [
        "https://chapelboro.com/feed/",
        "https://indyweek.com/feed/",
        "https://www.newsobserver.com/latest-news/?widgetName=rssfeed&widgetContentId=712015&getXmlFeed=true",
    ],
}

FEED_SOURCE_BY_URL: dict[str, str] = {
    "https://chapelboro.com/feed/": "Chapelboro",
    "https://indyweek.com/feed/": "INDY Week",
    "https://www.newsobserver.com/latest-news/?widgetName=rssfeed&widgetContentId=712015&getXmlFeed=true": "News & Observer",
}


def _region_slug(region: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", region.lower())
    return re.sub(r"[-\s]+", "-", slug).strip("-")


def _cache_path(region: str, feed_urls: list[str] | None = None) -> Path:
    slug = _region_slug(region)
    if feed_urls is not None:
        feed_key = hashlib.sha256("|".join(sorted(feed_urls)).encode()).hexdigest()[:12]
        slug = f"{slug}-{feed_key}"
    return _CACHE_DIR / f"{slug}.json"


def _parse_published(entry: feedparser.FeedParserDict) -> date | None:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        return datetime(*entry.published_parsed[:6]).date()
    if hasattr(entry, "updated_parsed") and entry.updated_parsed:
        return datetime(*entry.updated_parsed[:6]).date()
    published = entry.get("published") or entry.get("updated")
    if not published:
        return None
    try:
        return parsedate_to_datetime(published).date()
    except (TypeError, ValueError, OverflowError):
        return None


def _entry_text(entry: feedparser.FeedParserDict) -> str:
    if entry.get("summary"):
        return str(entry.summary).strip()
    content = entry.get("content")
    if content and isinstance(content, list) and content[0].get("value"):
        return str(content[0]["value"]).strip()
    return str(entry.get("title", "")).strip()


def _load_cache(region: str, feed_urls: list[str] | None = None) -> list[Article] | None:
    cache_path = _cache_path(region, feed_urls)
    if not cache_path.exists():
        return None
    data = json.loads(cache_path.read_text(encoding="utf-8"))
    return [Article(**article) for article in data]


def _write_cache(
    region: str,
    articles: list[Article],
    feed_urls: list[str] | None = None,
) -> None:
    cache_path = _cache_path(region, feed_urls)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    payload = [article.model_dump(mode="json") for article in articles]
    cache_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def _load_seed_fixture() -> list[Article]:
    fixture = resources.files("tools").joinpath(_SEED_FIXTURE)
    data = json.loads(fixture.read_text(encoding="utf-8"))
    return [Article(**article) for article in data]


def _feed_source(url: str) -> str:
    return FEED_SOURCE_BY_URL.get(url, url)


def _seed_articles_for_sources(sources: set[str]) -> list[Article]:
    return [article for article in _load_seed_fixture() if article.source in sources]


def _fetch_feed(url: str, *, source_name: str | None = None) -> list[Article]:
    response = httpx.get(url, timeout=_FETCH_TIMEOUT, follow_redirects=True)
    response.raise_for_status()
    parsed = feedparser.parse(response.text)
    source = source_name or parsed.feed.get("title") or url
    articles: list[Article] = []
    for entry in parsed.entries:
        link = entry.get("link")
        title = entry.get("title")
        if not link or not title:
            continue
        articles.append(
            Article(
                title=str(title).strip(),
                text=_entry_text(entry),
                url=str(link).strip(),
                source=str(source).strip(),
                published=_parse_published(entry),
            )
        )
    if not articles:
        raise ValueError(f"Feed returned no articles: {url}")
    return articles


def fetch_news(
    region: str,
    feed_urls: list[str] | None = None,
    *,
    use_cache: bool = True,
) -> list[Article]:
    """Fetch local news articles for a region, with disk cache and fixture fallback."""
    if use_cache:
        cached = _load_cache(region, feed_urls)
        if cached is not None:
            return cached

    urls = feed_urls or REGION_FEEDS.get(region, REGION_FEEDS[_DEFAULT_REGION])
    articles: list[Article] = []
    failed_sources: set[str] = set()
    for url in urls:
        source = _feed_source(url)
        try:
            articles.extend(_fetch_feed(url, source_name=source))
        except (httpx.HTTPError, ValueError):
            failed_sources.add(source)

    if not articles:
        articles = _load_seed_fixture()
    elif failed_sources:
        seen_urls = {article.url for article in articles}
        for article in _seed_articles_for_sources(failed_sources):
            if article.url not in seen_urls:
                articles.append(article)
                seen_urls.add(article.url)

    _write_cache(region, articles, feed_urls)
    return articles


if __name__ == "__main__":
    region = _DEFAULT_REGION
    cache_path = _cache_path(region)

    if cache_path.exists():
        cache_path.unlink()

    first = fetch_news(region)
    print(f"Fetched {len(first)} articles (live or fixture fallback)")
    print(f"First: {first[0].title} — {first[0].url}")
    assert all(isinstance(article, Article) for article in first)
    assert len(first) > 0
    assert cache_path.exists(), "Expected cache file after first fetch"

    second = fetch_news(region)
    print(f"Cached fetch returned {len(second)} articles instantly from {cache_path}")
    assert len(second) == len(first)
