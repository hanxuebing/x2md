"""Span-level text extraction and heading inference."""
from __future__ import annotations

import re
from collections import Counter
from statistics import median

from ..ir import Document, Line, Span, TextBlock


_BULLET_RE = re.compile(r"^\s*([•·●○▪◦\-–—*])\s+")
_ORDERED_RE = re.compile(r"^\s*(\d+[.)、]|[a-zA-Z][.)])\s+")


def _color_to_hex(c: int) -> str:
    return f"#{c:06x}"


def _font_flags(flags: int) -> tuple[bool, bool]:
    # PyMuPDF span flags: bit 4 (16) = bold; bit 1 (2) = italic.
    bold = bool(flags & 16)
    italic = bool(flags & 2)
    return bold, italic


def extract_text_blocks(fpage) -> list[TextBlock]:
    raw = fpage.get_text("dict", sort=True)
    blocks: list[TextBlock] = []

    for blk in raw.get("blocks", []):
        if blk.get("type", 0) != 0:
            continue  # 0 = text, 1 = image (handled in images.py)
        lines: list[Line] = []
        for line in blk.get("lines", []):
            spans: list[Span] = []
            for sp in line.get("spans", []):
                text = sp.get("text", "")
                if not text:
                    continue
                bold, italic = _font_flags(int(sp.get("flags", 0)))
                origin_raw = sp.get("origin")
                origin = (
                    (float(origin_raw[0]), float(origin_raw[1]))
                    if origin_raw is not None
                    else None
                )
                spans.append(
                    Span(
                        text=text,
                        font=sp.get("font", "") or "",
                        size=float(sp.get("size", 0.0)),
                        color=_color_to_hex(int(sp.get("color", 0))),
                        bold=bold,
                        italic=italic,
                        bbox=tuple(sp.get("bbox", line.get("bbox", (0, 0, 0, 0)))),  # type: ignore[arg-type]
                        origin=origin,
                    )
                )
            if spans:
                lines.append(Line(bbox=tuple(line.get("bbox", (0, 0, 0, 0))), spans=spans))  # type: ignore[arg-type]
        if not lines:
            continue
        text_block = TextBlock(bbox=tuple(blk.get("bbox", (0, 0, 0, 0))), lines=lines)  # type: ignore[arg-type]

        first_line_text = lines[0].text
        if _BULLET_RE.match(first_line_text):
            text_block.list_marker = "bullet"
        elif _ORDERED_RE.match(first_line_text):
            text_block.list_marker = "ordered"

        blocks.append(text_block)

    return blocks


def _block_dominant_size(block: TextBlock) -> float:
    sizes = [sp.size for line in block.lines for sp in line.spans if sp.text.strip()]
    if not sizes:
        return 0.0
    return float(median(sizes))


def _block_is_bold(block: TextBlock) -> bool:
    spans = [sp for line in block.lines for sp in line.spans if sp.text.strip()]
    if not spans:
        return False
    bold_chars = sum(len(sp.text) for sp in spans if sp.bold)
    total = sum(len(sp.text) for sp in spans)
    return total > 0 and bold_chars / total > 0.6


def infer_headings(doc: Document) -> None:
    """Assign heading_level (1..4) to TextBlocks using global font-size quantiles."""
    sizes: Counter[float] = Counter()
    blocks: list[TextBlock] = []
    for page in doc.pages:
        for blk in page.blocks:
            if isinstance(blk, TextBlock):
                size = _block_dominant_size(blk)
                if size > 0:
                    sizes[round(size, 1)] += 1
                    blocks.append(blk)

    if not sizes:
        return

    weighted: list[float] = []
    for sz, cnt in sizes.items():
        weighted.extend([sz] * cnt)
    body_size = float(median(weighted))

    distinct = sorted({sz for sz in sizes if sz > body_size}, reverse=True)
    size_to_level: dict[float, int] = {}
    for idx, sz in enumerate(distinct[:4]):
        size_to_level[sz] = idx + 1  # H1, H2, H3, H4

    for blk in blocks:
        size = round(_block_dominant_size(blk), 1)
        if size in size_to_level:
            blk.heading_level = size_to_level[size]
        elif size > body_size and _block_is_bold(blk) and len(blk.text) < 120:
            blk.heading_level = min(4, len(size_to_level) + 1) or 4
