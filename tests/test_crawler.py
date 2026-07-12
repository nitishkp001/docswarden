"""Crawler tests: pure link-dedup logic offline, async BFS crawl via mocked HTTP."""

import httpx
import pytest

from docwarden.crawler import _enqueue_new_links, crawl_recipe
from docwarden.recipes import Recipe, SourceConfig


def test_enqueue_new_links_dedupes_repeated_hrefs():
    seen = {"https://example.com/seed"}
    queue: list[str] = []
    html = '<a href="/a"></a><a href="/a"></a><a href="/b"></a>'

    _enqueue_new_links("https://example.com", html, seen, queue)

    assert queue == ["https://example.com/a", "https://example.com/b"]
    assert seen == {"https://example.com/seed", "https://example.com/a", "https://example.com/b"}


def test_enqueue_new_links_skips_already_seen_across_calls():
    # Simulates two different pages linking to the same targets — a shared page
    # must only ever be queued once, no matter how many referrers link to it.
    seen = {"https://example.com/seed"}
    queue: list[str] = []
    _enqueue_new_links("https://example.com", '<a href="/shared"></a>', seen, queue)
    _enqueue_new_links("https://example.com", '<a href="/shared"></a>', seen, queue)

    assert queue == ["https://example.com/shared"]  # queued once, not twice


def test_enqueue_new_links_ignores_hash_and_query_fragments():
    seen: set[str] = set()
    queue: list[str] = []
    html = '<a href="/page#section"></a><a href="/other?x=1"></a><a href="/plain"></a>'

    _enqueue_new_links("https://example.com", html, seen, queue)

    assert queue == ["https://example.com/plain"]


def _make_recipe(url: str, include: list[str]) -> Recipe:
    return Recipe(
        id="fake",
        name="Fake",
        homepage=url,
        source=SourceConfig(type="crawl", url=url, include=include, exclude=[]),
    )


_PAGES = {
    "/docs/seed": '<a href="/docs/a"></a><a href="/docs/b"></a>',
    "/docs/a": '<a href="/docs/shared"></a><a href="/docs/b"></a>',
    "/docs/b": '<a href="/docs/shared"></a><a href="/docs/a"></a>',
    "/docs/shared": '<a href="/docs/a"></a><a href="/docs/b"></a>',
    "/blog/unrelated": '<a href="/docs/seed"></a>',
}


def _handler(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    body = _PAGES.get(path)
    if body is None:
        return httpx.Response(404)
    return httpx.Response(200, text=f"<html><body>{body}</body></html>")


@pytest.mark.asyncio
async def test_crawl_site_bfs_collects_pages_and_respects_include_filter(monkeypatch):
    transport = httpx.MockTransport(_handler)
    real_async_client = httpx.AsyncClient

    def client_factory(*args, **kwargs):
        kwargs["transport"] = transport
        return real_async_client(*args, **kwargs)

    monkeypatch.setattr("docwarden.crawler.httpx.AsyncClient", client_factory)

    recipe = _make_recipe("https://example.com/docs/seed", ["/docs/**"])
    results = await crawl_recipe(recipe)

    urls = {url for url, _ in results}
    assert urls == {
        "https://example.com/docs/seed",
        "https://example.com/docs/a",
        "https://example.com/docs/b",
        "https://example.com/docs/shared",
    }
    # /blog/unrelated is never linked from any /docs/** page, and even if it were,
    # it's outside the include filter — must not appear.
    assert "https://example.com/blog/unrelated" not in urls
    # no duplicate fetches despite /docs/shared being linked from both a and b
    assert len(results) == len(urls)
