"""Image-backed HTML renderer: rasterized page background + invisible text layer.

Each page is shown as a high-resolution image (pixel-identical to the PDF), with a
transparent, absolutely-positioned text layer on top so the text stays selectable
and searchable. A small load-time script scales each text run horizontally to its
PDF width so selection highlights line up with the glyphs in the image.
"""
from __future__ import annotations

import html as html_mod
from pathlib import Path

from ..ir import Document, TextBlock
from .html_exact import _image_src, _rel_assets_dir  # noqa: F401  (shared helpers)


_BASE_CSS = """
* { box-sizing: border-box; }
body { margin: 0; background: #525659; }
.page { position: relative; background: #fff; margin: 16pt auto; box-shadow: 0 0 6pt rgba(0,0,0,0.4); overflow: hidden; }
.bg { position: absolute; left: 0; top: 0; }
.t { position: absolute; white-space: pre; color: transparent; transform-origin: left top; line-height: 1; font-family: serif; }
::selection { background: rgba(0,120,255,0.3); }
""".strip()


_FIT_SCRIPT = """
<script>
window.addEventListener('load', function () {
  var PT = 96 / 72;
  document.querySelectorAll('.t[data-w]').forEach(function (el) {
    var tw = parseFloat(el.getAttribute('data-w'));
    if (!(tw > 0)) return;
    var nw = el.getBoundingClientRect().width / PT;
    if (nw > 0) {
      var s = tw / nw;
      if (isFinite(s) && s > 0 && Math.abs(s - 1) > 0.005)
        el.style.transform = 'scaleX(' + s + ')';
    }
  });
});
</script>
""".strip()


def render_html_image(
    doc: Document,
    *,
    html_path: Path,
    assets_dir: Path | None = None,
) -> str:
    """Return an HTML string showing each page as an image with a hidden text layer.

    If ``assets_dir`` is given, page images are written there and referenced via
    relative URLs; otherwise they are inlined as data URIs.
    """
    assets_path = Path(assets_dir) if assets_dir is not None else None
    if assets_path is not None:
        assets_path.mkdir(parents=True, exist_ok=True)

    parts: list[str] = [
        "<!DOCTYPE html>",
        '<html lang="en"><head><meta charset="utf-8">',
        '<meta name="generator" content="pdf2x">',
        "<style>",
        _BASE_CSS,
        "</style></head><body>",
    ]

    for page in doc.pages:
        parts.append(
            f'<div class="page" id="p{page.index + 1}" '
            f'style="width:{page.width:.2f}pt;height:{page.height:.2f}pt;">'
        )
        res = doc.images.get(page.background_ref) if page.background_ref else None
        if res is not None:
            src = _image_src(res, html_path, assets_path)
            parts.append(
                f'<img class="bg" src="{src}" alt="" '
                f'style="width:{page.width:.2f}pt;height:{page.height:.2f}pt;">'
            )
        for block in page.blocks:
            if isinstance(block, TextBlock):
                parts.append(_render_text(block))
        parts.append("</div>")

    parts.append(_FIT_SCRIPT)
    parts.append("</body></html>")
    return "\n".join(parts)


def _render_text(block: TextBlock) -> str:
    out: list[str] = []
    for line in block.lines:
        for sp in line.spans:
            if not sp.text:
                continue
            x0, y0, x1, _y1 = sp.bbox
            width = x1 - x0
            style = (
                f"left:{x0:.2f}pt;top:{y0:.2f}pt;font-size:{sp.size:.2f}pt;"
            )
            out.append(
                f'<span class="t" style="{style}" data-w="{width:.2f}">'
                f"{html_mod.escape(sp.text)}</span>"
            )
    return "".join(out)
