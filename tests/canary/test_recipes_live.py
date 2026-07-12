"""Live recipe canary tests — catch site redesigns before users do.

NETWORK-GATED: only runs when RUN_CANARY=1 is set.
Never runs in the normal PR gate.

Usage:
    RUN_CANARY=1 uv run pytest tests/canary
"""

import os

import httpx
import pytest

from docwarden.parser import parse_page
from docwarden.recipes import load_recipes

pytestmark = pytest.mark.skipif(
    os.environ.get("RUN_CANARY") != "1",
    reason="Set RUN_CANARY=1 to run live recipe canary tests",
)


@pytest.fixture(scope="module")
def recipes():
    return {r.id: r for r in load_recipes()}


def _fetch(url: str) -> str:
    r = httpx.get(
        url, follow_redirects=True, timeout=20, headers={"User-Agent": "docwarden-canary/0.1"}
    )
    r.raise_for_status()
    return r.text


def test_fastapi_canary(recipes):
    r = recipes["fastapi"]
    url = r.canary["url"]
    marker = r.canary["marker"]
    html = _fetch(url)
    sections = parse_page(html, content_selector=r.parser.content_selector, url=url)
    full_text = " ".join(s.content for s in sections).lower()
    assert marker.lower() in full_text, (
        f"FastAPI canary failed: '{marker}' not found in extracted content from {url}. "
        "The docs site may have been redesigned — check content_selector in fastapi.yaml."
    )


def test_react_canary(recipes):
    r = recipes["react"]
    url = r.canary["url"]
    marker = r.canary["marker"]
    html = _fetch(url)
    sections = parse_page(html, content_selector=r.parser.content_selector, url=url)
    full_text = " ".join(s.content for s in sections).lower()
    assert marker.lower() in full_text, (
        f"React canary failed: '{marker}' not found in extracted content from {url}. "
        "Check content_selector in react.yaml."
    )


def test_nextjs_canary(recipes):
    r = recipes["nextjs"]
    url = r.canary["url"]
    marker = r.canary["marker"]
    html = _fetch(url)
    sections = parse_page(html, content_selector=r.parser.content_selector, url=url)
    full_text = " ".join(s.content for s in sections).lower()
    assert marker.lower() in full_text, (
        f"Next.js canary failed: '{marker}' not found in extracted content from {url}. "
        "Check content_selector in nextjs.yaml."
    )
