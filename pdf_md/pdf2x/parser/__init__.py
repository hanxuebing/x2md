"""Top-level PDF parser: glue PyMuPDF, pdfplumber, OCR fallback into a Document IR."""
from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Literal

import pymupdf  # type: ignore[import-untyped]

from ..ir import Document, ImageResource, Page
from ..fonts import collect_fonts
from .text import extract_text_blocks, infer_headings
from .tables import extract_tables, merge_tables_into_page
from .images import extract_images
from .ocr import ocr_page_if_needed


OcrMode = Literal["auto", "always", "off"]


def _collect_glyphmap(fpage, glyphmap: dict[str, dict[int, int]]) -> None:
    """Accumulate {font_name: {unicode_cp: glyph_id}} from a page's glyph trace.

    PyMuPDF's ``get_texttrace()`` exposes the actual glyph id used for each
    character, which embedded subset (CID-keyed) fonts need to rebuild a usable
    Unicode cmap before WOFF2 export. Without it the browser cannot map HTML
    text to glyphs and silently falls back to a system font.
    """
    try:
        spans = fpage.get_texttrace()
    except Exception:
        return
    for span in spans:
        font_name = span.get("font", "") or ""
        if not font_name:
            continue
        fmap = glyphmap.setdefault(font_name, {})
        for ch in span.get("chars", ()):  # (ucs, gid, origin, ...) per char
            if len(ch) < 2:
                continue
            ucs = int(ch[0])
            gid = int(ch[1])
            if gid == 0 or ucs < 32:
                continue
            fmap.setdefault(ucs, gid)


def _parse_page_spec(spec: str | None, n_pages: int) -> list[int]:
    if not spec:
        return list(range(n_pages))
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            start = int(a) - 1
            end = int(b) - 1
            out.update(range(max(0, start), min(n_pages, end + 1)))
        else:
            i = int(part) - 1
            if 0 <= i < n_pages:
                out.add(i)
    return sorted(out)


def parse_pdf(
    pdf_path: Path,
    *,
    ocr: OcrMode = "auto",
    ocr_lang: str = "eng",
    pages: str | None = None,
    page_images: bool = False,
    page_image_dpi: int = 144,
    embed_fonts: bool = True,
    on_page: Callable[[int, int], None] | None = None,
) -> Document:
    doc = Document()
    fitz_doc = pymupdf.open(pdf_path)
    try:
        page_indices = _parse_page_spec(pages, fitz_doc.page_count)
        total = len(page_indices)

        for new_idx, pno in enumerate(page_indices):
            fpage = fitz_doc.load_page(pno)
            page = Page(index=new_idx, width=fpage.rect.width, height=fpage.rect.height)

            text_blocks = extract_text_blocks(fpage)
            _collect_glyphmap(fpage, doc.font_glyphmap)

            ocr_blocks = ocr_page_if_needed(
                fpage, existing_blocks=text_blocks, mode=ocr, lang=ocr_lang
            )
            if ocr_blocks is not None:
                text_blocks = ocr_blocks

            image_blocks = extract_images(fpage, fitz_doc, doc.images)
            tables = extract_tables(pdf_path, pno)

            page.blocks = list(text_blocks) + list(image_blocks)
            merge_tables_into_page(page, tables)

            page.blocks.sort(key=lambda b: (round(b.bbox[1], 1), round(b.bbox[0], 1)))

            if page_images:
                zoom = page_image_dpi / 72.0
                pix = fpage.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
                ref = f"p{new_idx + 1}-page.png"
                doc.images[ref] = ImageResource(ref=ref, ext="png", data=pix.tobytes("png"))
                page.background_ref = ref

            doc.pages.append(page)

            if on_page is not None:
                on_page(new_idx + 1, total)

        infer_headings(doc)
        if embed_fonts:
            collect_fonts(doc, fitz_doc)
    finally:
        fitz_doc.close()

    return doc
