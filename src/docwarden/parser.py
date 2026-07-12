"""Parse HTML pages into ordered sections.

Pure/offline — no network, no filesystem side-effects. Testable with fixtures.

Output per page: list of Section(breadcrumb, section_title, anchor, content)
where content is clean prose + fenced code blocks.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from selectolax.parser import HTMLParser, Node


@dataclass
class Section:
    breadcrumb: str  # "Guide > Routing > Dynamic Segments"
    section_title: str
    anchor: str  # slug without '#'
    content: str  # prose + code, newline-separated
    level: int  # heading level (1-4) that opened this section


HEADING_TAGS = {"h1", "h2", "h3", "h4"}
HEADING_LEVELS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4}
BLOCK_TAGS = {"p", "li", "dd", "blockquote", "td", "dt"}
CONTAINER_TAGS = {
    "div",
    "section",
    "main",
    "article",
    "aside",
    "details",
    "summary",
    "ul",
    "ol",
    "dl",
    "table",
    "tbody",
    "tr",
    "thead",
}
STRIP_TAGS = {"script", "style", "nav", "footer", "header", "noscript"}


def parse_page(html: str, content_selector: str = "article", url: str = "") -> list[Section]:
    """Parse an HTML page into structured sections."""
    tree = HTMLParser(html)

    for tag in STRIP_TAGS:
        for node in tree.css(tag):
            node.decompose()
    for node in tree.css("[aria-hidden='true']"):
        node.decompose()

    root = tree.css_first(content_selector)
    if root is None:
        root = tree.css_first("body") or tree.root

    page_title = _page_title(tree, url)
    sections = _collect_sections(root, page_title)
    return sections


def _page_title(tree: HTMLParser, url: str) -> str:
    h1 = tree.css_first("h1")
    if h1:
        return h1.text(strip=True)
    title = tree.css_first("title")
    if title:
        t = title.text(strip=True)
        return t.split("|")[0].strip() or t
    return url


def _collect_sections(root: Node, page_title: str) -> list[Section]:
    """Walk DOM children, splitting on headings, collecting content blocks."""
    sections: list[Section] = []
    # stack entries: (level, title, anchor)
    breadcrumb_stack: list[tuple[int, str, str]] = [(1, page_title, "")]
    current_heading: tuple[int, str, str] = (1, page_title, "")
    current_blocks: list[str] = []

    def flush() -> None:
        text = "\n\n".join(b for b in current_blocks if b.strip())
        if not text.strip():
            return
        level, title, anchor = current_heading
        bc = _make_breadcrumb(breadcrumb_stack, level, title)
        sections.append(
            Section(
                breadcrumb=bc,
                section_title=title,
                anchor=anchor,
                content=text,
                level=level,
            )
        )

    def walk(node: Node) -> None:
        """Depth-first walk; yields content into current_blocks."""
        child = node.child
        while child:
            tag = child.tag

            if tag in STRIP_TAGS:
                child = child.next
                continue

            if tag in HEADING_TAGS:
                flush()
                current_blocks.clear()
                level = HEADING_LEVELS[tag]
                title = child.text(strip=True)
                anchor = _extract_anchor(child)
                # unwind stack to levels above this one
                while breadcrumb_stack and breadcrumb_stack[-1][0] >= level:
                    breadcrumb_stack.pop()
                breadcrumb_stack.append((level, title, anchor))
                nonlocal current_heading
                current_heading = (level, title, anchor)

            elif tag == "pre":
                code = _extract_code(child)
                if code:
                    current_blocks.append(f"```\n{code}\n```")

            elif tag in BLOCK_TAGS:
                text = _node_text(child)
                if text.strip():
                    current_blocks.append(text)

            elif tag in CONTAINER_TAGS:
                walk(child)

            # bare text nodes at block level (selectolax uses '-text' tag)
            elif tag == "-text":
                t = (child.text() or "").strip()
                if t:
                    current_blocks.append(t)

            child = child.next

    walk(root)
    flush()
    return sections


def _make_breadcrumb(stack: list[tuple[int, str, str]], level: int, title: str) -> str:
    parts = [s[1] for s in stack if s[0] < level]
    parts.append(title)
    return " > ".join(parts)


def _extract_anchor(node: Node) -> str:
    node_id = node.attributes.get("id", "")
    if node_id:
        return node_id
    child_a = node.css_first("a[id], a[name]")
    if child_a:
        return child_a.attributes.get("id") or child_a.attributes.get("name") or ""
    return _slugify(node.text(strip=True))


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _extract_code(pre_node: Node) -> str:
    code = pre_node.css_first("code")
    target = code if code else pre_node
    return target.text(strip=False).rstrip()


def _node_text(node: Node) -> str:
    """Text content of a block element, skipping nested pre blocks."""
    # selectolax's node.text(strip=True) walks all descendants — use it directly.
    # Inline <code> within prose is fine to include; <pre> blocks are block-level
    # and won't appear inside <p>/<li>/<td> in well-formed docs HTML.
    return node.text(strip=True)
