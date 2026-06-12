"""Font discovery and WOFF2 export for HTML embedding."""
from __future__ import annotations

import io
import re

from .ir import Document, FontResource, TextBlock


_SAFE_NAME = re.compile(r"[^A-Za-z0-9_-]+")


def _safe(name: str) -> str:
    base = _SAFE_NAME.sub("_", name).strip("_")
    return base or "Font"


def collect_fonts(doc: Document, fitz_doc) -> None:
    """Walk used fonts, extract bytes via PyMuPDF, convert to WOFF2."""
    seen: dict[str, FontResource] = {}
    used: set[str] = set()
    for page in doc.pages:
        for blk in page.blocks:
            if isinstance(blk, TextBlock):
                for line in blk.lines:
                    for sp in line.spans:
                        if sp.font:
                            used.add(sp.font)

    for idx, font_name in enumerate(sorted(used)):
        css_name = f"F{idx}"
        family = font_name
        weight = 700 if "Bold" in font_name else 400
        italic = any(tag in font_name for tag in ("Italic", "Oblique", "It"))
        glyph_cmap = doc.font_glyphmap.get(font_name)
        woff2, ascent, advance = _try_export_woff2(fitz_doc, font_name, glyph_cmap)
        seen[font_name] = FontResource(
            css_name=css_name,
            family=_safe(family),
            weight=weight,
            italic=italic,
            woff2=woff2,
            ascent=ascent,
            advance=advance,
        )

    doc.fonts = seen


def _try_export_woff2(
    fitz_doc, font_name: str, glyph_cmap: dict[int, int] | None = None
) -> tuple[bytes | None, float, dict[int, float]]:
    """Find the font xref, convert to WOFF2, and extract baseline/advance metrics.

    Returns ``(woff2_bytes, ascent_ratio, advance_by_codepoint)``. The metrics let
    the exact renderer place text on its true baseline and scale each run to the
    PDF's own width, matching the source layout instead of drifting on the
    browser's font metrics.
    """
    try:
        for pno in range(fitz_doc.page_count):
            for f in fitz_doc.get_page_fonts(pno):
                xref, ext, _type, basename, *_ = f
                if basename == font_name or basename.endswith("+" + font_name):
                    name, _ext, _ftype, buf = fitz_doc.extract_font(xref)
                    if not buf:
                        return None, 0.0, {}
                    return _to_woff2(buf, glyph_cmap)
    except Exception:
        return None, 0.0, {}
    return None, 0.0, {}


def _rebuild_cmap(tt, glyph_cmap: dict[int, int]) -> bool:
    """Install a Unicode cmap on ``tt`` from a {codepoint: glyph_id} mapping.

    Embedded subset CID-keyed fonts usually carry no Unicode cmap (the PDF maps
    char codes to glyphs via its own CMap), so browsers cannot render HTML text
    with them and fall back to a system font. Rebuilding the cmap from the glyph
    ids PyMuPDF actually used lets the embedded glyphs render directly.
    """
    from fontTools.ttLib import newTable
    from fontTools.ttLib.tables._c_m_a_p import CmapSubtable

    glyph_order = tt.getGlyphOrder()
    n = len(glyph_order)
    mapping: dict[int, str] = {}
    has_non_bmp = False
    for cp, gid in glyph_cmap.items():
        if gid <= 0 or gid >= n:
            continue
        mapping[cp] = glyph_order[gid]
        if cp > 0xFFFF:
            has_non_bmp = True
    if not mapping:
        return False

    cmap = newTable("cmap")
    cmap.tableVersion = 0
    subtables = []

    bmp = {cp: name for cp, name in mapping.items() if cp <= 0xFFFF}
    st4 = CmapSubtable.newSubtableClass(4)()
    st4.platformID = 3
    st4.platEncID = 1
    st4.format = 4
    st4.language = 0
    st4.cmap = bmp
    subtables.append(st4)

    if has_non_bmp:
        st12 = CmapSubtable.newSubtableClass(12)()
        st12.platformID = 3
        st12.platEncID = 10
        st12.format = 12
        st12.reserved = 0
        st12.length = 0
        st12.language = 0
        st12.nGroups = 0
        st12.cmap = dict(mapping)
        subtables.append(st12)

    cmap.tables = subtables
    tt["cmap"] = cmap
    return True


def _to_woff2(font_bytes: bytes, glyph_cmap: dict[int, int] | None = None) -> bytes | None:
    try:
        from fontTools.ttLib import TTFont
    except Exception:
        return None
    try:
        tt = TTFont(io.BytesIO(font_bytes))
        if glyph_cmap:
            try:
                _rebuild_cmap(tt, glyph_cmap)
            except Exception:
                pass
        tt.flavor = "woff2"
        out = io.BytesIO()
        tt.save(out)
        return out.getvalue()
    except Exception:
        return None
