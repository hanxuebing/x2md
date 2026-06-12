"""Pixel-faithful HTML renderer: absolute-positioned spans, embedded fonts."""
from __future__ import annotations

import base64
import html as html_mod
from pathlib import Path

from ..ir import Document, ImageBlock, ImageResource, TableBlock, TextBlock


_BASE_CSS = """
* { box-sizing: border-box; }
body { margin: 0; background: #525659; font-family: serif; color: #000; }
.page { position: relative; background: #fff; margin: 16pt auto; box-shadow: 0 0 6pt rgba(0,0,0,0.4); overflow: hidden; }
.t { position: absolute; white-space: pre; transform-origin: left top; line-height: 1; }
.t.b { font-weight: bold; }
.t.i { font-style: italic; }
.img { position: absolute; }
table.x { position: absolute; border-collapse: collapse; font-size: 9pt; background: transparent; }
table.x td, table.x th { border: 1pt solid #888; padding: 1pt 3pt; vertical-align: top; }
""".strip()


def render_html_exact(
    doc: Document,
    *,
    html_path: Path,
    assets_dir: Path | None = None,
) -> str:
    """Return an HTML string that visually mirrors the source PDF.

    If ``assets_dir`` is given, images and WOFF2 fonts are written there and
    referenced via relative URLs; otherwise they are inlined as data URIs.
    """
    assets_path = Path(assets_dir) if assets_dir is not None else None
    if assets_path is not None:
        assets_path.mkdir(parents=True, exist_ok=True)

    font_face_css: list[str] = []
    for font in doc.fonts.values():
        if not font.woff2:
            continue
        if assets_path is not None:
            file_name = f"{font.css_name}.woff2"
            (assets_path / file_name).write_bytes(font.woff2)
            rel = _rel_assets_dir(html_path, assets_path)
            src = f"url('{rel}/{file_name}') format('woff2')"
        else:
            b64 = base64.b64encode(font.woff2).decode("ascii")
            src = f"url(data:font/woff2;base64,{b64}) format('woff2')"
        style = "italic" if font.italic else "normal"
        font_face_css.append(
            f"@font-face {{ font-family: '{font.css_name}'; "
            f"font-style: {style}; font-weight: {font.weight}; src: {src}; }}"
        )

    parts: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="generator" content="pdf2x">',
        "<style>",
        _BASE_CSS,
        *font_face_css,
        "</style></head><body>",
    ]

    for page in doc.pages:
        parts.append(
            f'<div class="page" id="p{page.index + 1}" '
            f'style="width:{page.width:.2f}pt;height:{page.height:.2f}pt;">'
        )
        for block in page.blocks:
            if isinstance(block, TextBlock):
                parts.append(_render_text(block, doc))
            elif isinstance(block, TableBlock):
                parts.append(_render_table(block))
            elif isinstance(block, ImageBlock):
                parts.append(_render_image(block, doc, html_path, assets_path))
        parts.append("</div>")

    parts.append("</body></html>")
    return "\n".join(parts)


def _render_text(block: TextBlock, doc: Document) -> str:
    out: list[str] = []
    for line in block.lines:
        for sp in line.spans:
            if not sp.text:
                continue
            x0, y0, _x1, _y1 = sp.bbox
            classes = ["t"]
            if sp.bold:
                classes.append("b")
            if sp.italic:
                classes.append("i")
            font = doc.fonts.get(sp.font)
            if font and font.woff2:
                family = f"'{font.css_name}', serif"
            else:
                family = "serif"
            style = (
                f"left:{x0:.2f}pt;top:{y0:.2f}pt;"
                f"font-family:{family};"
                f"font-size:{sp.size:.2f}pt;"
                f"color:{sp.color};"
            )
            out.append(
                f'<span class="{" ".join(classes)}" style="{style}">'
                f"{html_mod.escape(sp.text)}</span>"
            )
    return "".join(out)


def _render_table(block: TableBlock) -> str:
    x0, y0, x1, _y1 = block.bbox
    out = [
        f'<table class="x" style="left:{x0:.2f}pt;top:{y0:.2f}pt;'
        f'width:{x1 - x0:.2f}pt;">'
    ]
    for i, row in enumerate(block.rows):
        out.append("<tr>")
        tag = "th" if i == 0 else "td"
        for cell in row:
            out.append(f"<{tag}>{html_mod.escape(cell or '')}</{tag}>")
        out.append("</tr>")
    out.append("</table>")
    return "".join(out)


def _render_image(
    block: ImageBlock,
    doc: Document,
    html_path: Path,
    assets_path: Path | None,
) -> str:
    res = doc.images.get(block.image_ref)
    if res is None:
        return ""
    x0, y0, x1, y1 = block.bbox
    style = (
        f"left:{x0:.2f}pt;top:{y0:.2f}pt;"
        f"width:{x1 - x0:.2f}pt;height:{y1 - y0:.2f}pt;"
    )
    src = _image_src(res, html_path, assets_path)
    return f'<img class="img" style="{style}" src="{src}" alt="">'


def _image_src(
    res: ImageResource, html_path: Path, assets_path: Path | None
) -> str:
    if assets_path is not None:
        (assets_path / res.ref).write_bytes(res.data)
        rel = _rel_assets_dir(html_path, assets_path)
        return f"{rel}/{res.ref}"
    b64 = base64.b64encode(res.data).decode("ascii")
    mime = "image/jpeg" if res.ext in ("jpg", "jpeg") else f"image/{res.ext}"
    return f"data:{mime};base64,{b64}"


def _rel_assets_dir(html_path: Path, assets_path: Path) -> str:
    try:
        return assets_path.resolve().relative_to(html_path.resolve().parent).as_posix()
    except ValueError:
        return assets_path.name
