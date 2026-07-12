"""Crawl docs pages from a sitemap or local folder.

This is the ONLY module that does network I/O.
Parser/chunker/indexer are pure and offline-testable.
"""

import asyncio
import fnmatch
import re
from urllib.parse import urlparse, urlunparse

import httpx

from .recipes import Recipe

_USER_AGENT = "docwarden/0.1 (+https://github.com/nitish/docwarden; docs indexer)"
_CONCURRENCY = 5
_RATE_DELAY = 0.2  # seconds between requests per host


async def _fetch(client: httpx.AsyncClient, url: str) -> str | None:
    try:
        r = await client.get(url, follow_redirects=True, timeout=15)
        r.raise_for_status()
        return r.text
    except Exception as exc:
        print(f"  [skip] {url}: {exc}")
        return None


def _sitemap_urls(xml: str) -> list[str]:
    return re.findall(r"<loc>\s*(https?://[^<]+)\s*</loc>", xml)


def _matches_glob(path: str, patterns: list[str]) -> bool:
    for pat in patterns:
        if fnmatch.fnmatch(path, pat) or fnmatch.fnmatch(path, pat.rstrip("/") + "/"):
            return True
    return False


def _filter_urls(urls: list[str], include: list[str], exclude: list[str]) -> list[str]:
    result = []
    for url in urls:
        path = urlparse(url).path
        if exclude and _matches_glob(path, exclude):
            continue
        if include and not _matches_glob(path, include):
            continue
        result.append(url)
    return result


async def _check_robots(client: httpx.AsyncClient, base_url: str) -> set[str]:
    """Return disallowed paths from robots.txt (best-effort)."""
    parsed = urlparse(base_url)
    robots_url = urlunparse((parsed.scheme, parsed.netloc, "/robots.txt", "", "", ""))
    disallowed: set[str] = set()
    try:
        r = await client.get(robots_url, timeout=10)
        if r.status_code == 200:
            ua_active = False
            for line in r.text.splitlines():
                line = line.strip()
                if line.lower().startswith("user-agent:"):
                    agent = line.split(":", 1)[1].strip()
                    ua_active = agent in ("*", "docwarden")
                elif ua_active and line.lower().startswith("disallow:"):
                    path = line.split(":", 1)[1].strip()
                    if path:
                        disallowed.add(path)
    except Exception:
        pass
    return disallowed


def _is_disallowed(path: str, disallowed: set[str]) -> bool:
    return any(path.startswith(d) for d in disallowed)


async def crawl_recipe(recipe: Recipe) -> list[tuple[str, str]]:
    """Return list of (url, html) for all pages matching the recipe."""
    headers = {"User-Agent": _USER_AGENT}
    limits = httpx.Limits(max_connections=_CONCURRENCY, max_keepalive_connections=_CONCURRENCY)

    async with httpx.AsyncClient(headers=headers, limits=limits) as client:
        if recipe.source.type == "sitemap":
            return await _crawl_sitemap(client, recipe)
        if recipe.source.type == "crawl":
            return await _crawl_site(client, recipe)
        if recipe.source.type == "local":
            return _crawl_local(recipe)
    return []


async def _crawl_sitemap(client: httpx.AsyncClient, recipe: Recipe) -> list[tuple[str, str]]:
    assert recipe.source.url
    print(f"  Fetching sitemap: {recipe.source.url}")
    xml = await _fetch(client, recipe.source.url)
    if not xml:
        return []

    all_urls = _sitemap_urls(xml)
    # handle sitemap index (sitemap of sitemaps)
    if not all_urls:
        sub_urls = re.findall(r"<sitemap>.*?<loc>(https?://[^<]+)</loc>", xml, re.DOTALL)
        for sub_url in sub_urls:
            sub_xml = await _fetch(client, sub_url)
            if sub_xml:
                all_urls.extend(_sitemap_urls(sub_xml))

    filtered = _filter_urls(all_urls, recipe.source.include, recipe.source.exclude)
    filtered = list(dict.fromkeys(filtered))  # dedupe, preserve order

    base = recipe.source.url
    disallowed = await _check_robots(client, base)
    filtered = [u for u in filtered if not _is_disallowed(urlparse(u).path, disallowed)]

    print(f"  Crawling {len(filtered)} pages...")
    return await _fetch_all(client, filtered)


async def _crawl_site(client: httpx.AsyncClient, recipe: Recipe) -> list[tuple[str, str]]:
    # Basic BFS crawl — used when no sitemap is available.
    assert recipe.source.url
    from urllib.parse import urljoin

    visited: set[str] = set()
    queue = [recipe.source.url]
    results: list[tuple[str, str]] = []
    disallowed = await _check_robots(client, recipe.source.url)

    while queue:
        batch, queue = queue[:_CONCURRENCY], queue[_CONCURRENCY:]
        for url in batch:
            if url in visited:
                continue
            visited.add(url)
            path = urlparse(url).path
            if _is_disallowed(path, disallowed):
                continue
            if recipe.source.include and not _matches_glob(path, recipe.source.include):
                continue
            if recipe.source.exclude and _matches_glob(path, recipe.source.exclude):
                continue
            html = await _fetch(client, url)
            if html:
                results.append((url, html))
                # discover internal links (minimal)
                new = re.findall(r'href="(/[^"#?]+)"', html)
                base = recipe.source.url.rstrip("/")
                queue.extend(urljoin(base, p) for p in new if urljoin(base, p) not in visited)
        await asyncio.sleep(_RATE_DELAY)

    return results


def _crawl_local(recipe: Recipe) -> list[tuple[str, str]]:
    from pathlib import Path

    assert recipe.source.path
    base = Path(recipe.source.path)
    results = []
    for p in sorted(base.rglob("*.md")):
        url = f"local://{p.relative_to(base)}"
        results.append((url, p.read_text()))
    return results


async def _fetch_all(client: httpx.AsyncClient, urls: list[str]) -> list[tuple[str, str]]:
    sem = asyncio.Semaphore(_CONCURRENCY)

    async def fetch_one(url: str) -> tuple[str, str] | None:
        async with sem:
            await asyncio.sleep(_RATE_DELAY)
            html = await _fetch(client, url)
            return (url, html) if html else None

    tasks = [fetch_one(url) for url in urls]
    results = await asyncio.gather(*tasks)
    return [r for r in results if r is not None]
