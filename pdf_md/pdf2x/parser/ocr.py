"""OCR fallback for scanned/image-only PDF pages."""
from __future__ import annotations

import io
from typing import Literal

from ..ir import Line, Span, TextBlock


OcrMode = Literal["auto", "always", "off"]

_MIN_TEXT_LEN = 50


def _existing_text_length(blocks: list[TextBlock]) -> int:
    return sum(len(blk.text) for blk in blocks)


def ocr_page_if_needed(
    fpage,
    *,
    existing_blocks: list[TextBlock],
    mode: OcrMode,
    lang: str,
) -> list[TextBlock] | None:
    if mode == "off":
        return None
    if mode == "auto" and _existing_text_length(existing_blocks) >= _MIN_TEXT_LEN:
        return None

    try:
        import pytesseract  # type: ignore[import-untyped]
        from PIL import Image
    except Exception:
        return None

    try:
        pix = fpage.get_pixmap(dpi=300)
        img = Image.open(io.BytesIO(pix.tobytes("png")))
        data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)
    except Exception:
        return None

    scale_x = fpage.rect.width / pix.width
    scale_y = fpage.rect.height / pix.height

    by_block: dict[tuple[int, int, int], list[tuple[int, str, tuple[float, float, float, float]]]] = {}
    n = len(data.get("text", []))
    for i in range(n):
        txt = (data["text"][i] or "").strip()
        if not txt:
            continue
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        x = data["left"][i] * scale_x
        y = data["top"][i] * scale_y
        w = data["width"][i] * scale_x
        h = data["height"][i] * scale_y
        by_block.setdefault(key, []).append((data["word_num"][i], txt, (x, y, x + w, y + h)))

    blocks_by_par: dict[tuple[int, int], list[Line]] = {}
    for (bn, pn, ln), words in by_block.items():
        words.sort(key=lambda w: w[0])
        spans = [
            Span(
                text=t + " ",
                font="OCR",
                size=12.0,
                color="#000000",
                bold=False,
                italic=False,
                bbox=bb,
            )
            for _, t, bb in words
        ]
        if not spans:
            continue
        x0 = min(s.bbox[0] for s in spans)
        y0 = min(s.bbox[1] for s in spans)
        x1 = max(s.bbox[2] for s in spans)
        y1 = max(s.bbox[3] for s in spans)
        line = Line(bbox=(x0, y0, x1, y1), spans=spans)
        blocks_by_par.setdefault((bn, pn), []).append(line)

    out: list[TextBlock] = []
    for lines in blocks_by_par.values():
        lines.sort(key=lambda ln: ln.bbox[1])
        x0 = min(ln.bbox[0] for ln in lines)
        y0 = min(ln.bbox[1] for ln in lines)
        x1 = max(ln.bbox[2] for ln in lines)
        y1 = max(ln.bbox[3] for ln in lines)
        out.append(TextBlock(bbox=(x0, y0, x1, y1), lines=lines))
    return out
