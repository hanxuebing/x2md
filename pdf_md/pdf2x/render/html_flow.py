"""Semantic, flow-style HTML renderer (no absolute positioning)."""
from __future__ import annotations

import base64
import html as html_mod
from pathlib import Path

from ..ir import Document, ImageBlock, ImageResource, TableBlock, TextBlock


_CSS = """
body { font-family: serif; max-width: 800px; margin: 2em auto; padding: 0 1em; line-height: 1.5; color: #111; }
h1, h2, h3, h4 { line-height: 1.25; }
table { border-collapse: collapse; margin: 1em 0; }
td, th { border: 1px solid #999; padding: 4px 8px; }
img { max-width: 100%; height: auto; display: block; margin: 1em 0; }
.b { font-weight: bold; }
.i { font-style: italic; }
.page-break { border: 0; border-top: 1px dashed #ccc; margin: 2em 0; }
""".strip()


def render_html_flow(
    doc: Document,
    *,
    html_path: Path,
    assets_dir: Path | None = None,
) -> str:
    assets_path = Path(assets_dir) if assets_dir is not None else None
    if assets_path is not None:
        assets_path.mkdir(parents=True, exist_ok=True)

    parts: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="generator" content="pdf2x">',
        f"<style>{_CSS}</style></head><body>",
    ]

    for page_idx, page in enumerate(doc.pages):
        if page_idx > 0:
            parts.append('<hr class="page-break">')
        for block in page.blocks:
            if isinstance(block, TextBlock):
                parts.append(_render_text(block))
            elif isinstance(block, TableBlock):
                parts.append(_render_table(block))
            elif isinstance(block, ImageBlock):
                parts.append(_render_image(block, doc, html_path, assets_path))

    parts.append("</body></html>")
    return "\n".join(parts)


def _render_text(block: TextBlock) -> str:
    pieces: list[str] = []
    for line in block.lines:
        for sp in line.spans:
            piece = html_mod.escape(sp.text)
            if sp.bold and sp.italic:
                piece = f'<span class="b i">{piece}</span>'
            elif sp.bold:
                piece = f'<span class="b">{piece}</span>'
            elif sp.italic:
                piece = f'<span class="i">{piece}</span>'
            pieces.append(piece)
        pieces.append(" ")
    text = "".join(pieces).strip()
    if not text:
        return ""
    if block.heading_level:
        level = max(1, min(4, block.heading_level))
        return f"<h{level}>{text}</h{level}>"
    return f"<p>{text}</p>"


def _render_table(block: TableBlock) -> str:
    if not block.rows:
        return ""
    out = ["<table>"]
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
    src = _image_src(res, html_path, assets_path)
    return f'<img src="{src}" alt="">'


def _image_src(
    res: ImageResource, html_path: Path, assets_path: Path | None
) -> str:
    if assets_path is not None:
        (assets_path / res.ref).write_bytes(res.data)
        try:
            rel = (
                assets_path.resolve()
                .relative_to(html_path.resolve().parent)
                .as_posix()
            )
        except ValueError:
            rel = assets_path.name
        return f"{rel}/{res.ref}"
    b64 = base64.b64encode(res.data).decode("ascii")
    mime = "image/jpeg" if res.ext in ("jpg", "jpeg") else f"image/{res.ext}"
    return f"data:{mime};base64,{b64}"
