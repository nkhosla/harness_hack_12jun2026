"""Social fixture loader for the Issue Scout (WS-1.2).

Loads seeded social-signal posts from a JSON fixture and returns `list[Post]`.
`Post` mirrors the news `Article` shape (title/text/url) so the Scout clusterer
(1.3) can treat news and social signal uniformly, plus two optional social-only
fields (platform, author).
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict

DEFAULT_SOCIAL_FIXTURE = "social.sample.json"
_BUNDLED_FIXTURE = (
    Path(__file__).resolve().parent / "data" / DEFAULT_SOCIAL_FIXTURE
)


class Post(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str                   # short headline / first line — mirrors Article.title
    text: str                    # full post body          — mirrors Article.text
    url: str                     # permalink               — mirrors Article.url
    platform: str | None = None  # e.g. "x", "facebook", "nextdoor", "reddit"
    author: str | None = None    # handle / display name


def load_posts(path: str | Path | None = None) -> list[Post]:
    """Load seeded social posts from `path` (a JSON array of post objects).

    When `path` is omitted, reads the bundled fixture colocated with this
    module (``tools/data/social.sample.json``), which is included in the
    installed wheel via package data.

    Raises FileNotFoundError if the fixture is missing and pydantic
    ValidationError if any record violates the Post shape (strict: extra
    keys are rejected) — fail loud, matching the repo's strict-schema discipline.
    """
    if path is None:
        text = _BUNDLED_FIXTURE.read_text(encoding="utf-8")
    else:
        text = Path(path).read_text(encoding="utf-8")
    raw = json.loads(text)
    return [Post.model_validate(item) for item in raw]


if __name__ == "__main__":
    posts = load_posts()
    assert posts, "expected at least one seeded post"
    assert all(isinstance(p, Post) for p in posts)
    print(f"✓ loaded {len(posts)} social posts from {DEFAULT_SOCIAL_FIXTURE}")
