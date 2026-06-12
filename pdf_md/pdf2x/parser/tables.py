"""Table extraction via pdfplumber, merged into the page IR."""
from __future__ import annotations

from pathlib import Path

from ..ir import Page, TableBlock, TextBlock


def extract_tables(pdf_path: Path, page_index: int) -> list[TableBlock]:
    try:
        import pdfplumber  # type: ignore[import-untyped]
    except Exception:
        return []

    out: list[TableBlock] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if page_index >= len(pdf.pages):
                return []
            ppage = pdf.pages[page_index]
            for tbl in ppage.find_tables() or []:
                rows = tbl.extract() or []
                rows = [[(cell or "").strip() for cell in row] for row in rows]
                if not rows or not any(any(cell for cell in row) for row in rows):
                    continue
                bbox = tuple(float(x) for x in tbl.bbox)
                out.append(TableBlock(bbox=bbox, rows=rows))  # type: ignore[arg-type]
    except Exception:
        return []
    return out


def _overlaps(a, b, tol: float = 1.0) -> bool:
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    return not (ax1 < bx0 - tol or bx1 < ax0 - tol or ay1 < by0 - tol or by1 < ay0 - tol)


def merge_tables_into_page(page: Page, tables: list[TableBlock]) -> None:
    """Drop TextBlocks overlapping a table region, then append the tables."""
    if not tables:
        return
    kept = []
    for blk in page.blocks:
        if isinstance(blk, TextBlock) and any(
            _overlaps(blk.bbox, tbl.bbox) for tbl in tables
        ):
            continue
        kept.append(blk)
    kept.extend(tables)
    page.blocks = kept
