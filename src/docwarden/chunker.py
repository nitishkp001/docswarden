"""Split parsed sections into retrieval-sized chunks.

Rules:
- Chunk on H2/H3 section boundaries (already split by parser).
- Never split a code block from its introducing paragraph.
- Carry the full breadcrumb into every chunk.
- Soft cap: ~1200 tokens (~4800 chars). Overflow splits on paragraph boundaries
  and repeats the breadcrumb.
- Empty/whitespace-only sections are dropped.

Pure/offline — takes Section objects, returns Chunk objects.
"""

from __future__ import annotations

from dataclasses import dataclass

from .parser import Section

SOFT_MAX_CHARS = 4800  # ~1200 tokens


@dataclass
class Chunk:
    breadcrumb: str
    section_title: str
    anchor: str
    content: str
    ord: int  # order within source page


def chunk_sections(sections: list[Section]) -> list[Chunk]:
    """Convert a page's sections into a flat list of retrieval chunks."""
    chunks: list[Chunk] = []
    for section in sections:
        content = section.content.strip()
        if not content:
            continue
        if len(content) <= SOFT_MAX_CHARS:
            chunks.append(
                Chunk(
                    breadcrumb=section.breadcrumb,
                    section_title=section.section_title,
                    anchor=section.anchor,
                    content=content,
                    ord=len(chunks),
                )
            )
        else:
            chunks.extend(_split_large_section(section, start_ord=len(chunks)))
    return chunks


def _split_large_section(section: Section, start_ord: int) -> list[Chunk]:
    """Split an oversized section on paragraph boundaries, keeping code+prose together."""
    paragraphs = _split_paragraphs(section.content)
    groups: list[list[str]] = []
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para)
        # If adding this para would exceed cap AND we already have content,
        # but ONLY if the para isn't a code block being glued to prior prose.
        over_limit = current_len + para_len > SOFT_MAX_CHARS
        if over_limit and current and not _is_code_continuation(current, para):
            groups.append(current)
            current = [para]
            current_len = para_len
        else:
            current.append(para)
            current_len += para_len

    if current:
        groups.append(current)

    return [
        Chunk(
            breadcrumb=section.breadcrumb,
            section_title=section.section_title,
            anchor=section.anchor,
            content="\n\n".join(group),
            ord=start_ord + i,
        )
        for i, group in enumerate(groups)
        if "".join(group).strip()
    ]


def _split_paragraphs(content: str) -> list[str]:
    """Split on blank lines, preserving fenced code blocks as single units."""
    paras: list[str] = []
    current_lines: list[str] = []
    in_code = False

    for line in content.splitlines():
        if line.startswith("```"):
            in_code = not in_code
            current_lines.append(line)
            continue

        if in_code:
            current_lines.append(line)
            continue

        if line.strip() == "" and current_lines:
            paras.append("\n".join(current_lines))
            current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        paras.append("\n".join(current_lines))

    return [p for p in paras if p.strip()]


def _is_code_continuation(current: list[str], next_para: str) -> bool:
    """True if next_para is a code block that should stay glued to the last prose para."""
    if not next_para.startswith("```"):
        return False
    # Only glue if the last item in current is NOT already a code block
    last = current[-1] if current else ""
    return not last.startswith("```")
