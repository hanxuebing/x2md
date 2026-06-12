from pathlib import Path

from pdf2x.ir import Document, ImageResource, Line, Page, Span, TextBlock
from pdf2x.render.html_image import render_html_image


def _doc_with_background() -> Document:
    span = Span(
        text="序言 Palantir",
        font="F1",
        size=12.0,
        color="#000000",
        bold=False,
        italic=False,
        bbox=(90.0, 100.0, 200.0, 114.0),
    )
    line = Line(bbox=(90.0, 100.0, 200.0, 114.0), spans=[span])
    block = TextBlock(bbox=(90.0, 100.0, 200.0, 114.0), lines=[line])
    page = Page(
        index=0,
        width=595.0,
        height=842.0,
        blocks=[block],
        background_ref="p1-page.png",
    )
    doc = Document(pages=[page])
    doc.images["p1-page.png"] = ImageResource(
        ref="p1-page.png", ext="png", data=b"\x89PNG\r\n\x1a\n"
    )
    return doc


def test_html_image_has_background_and_text_layer(tmp_path: Path) -> None:
    out = render_html_image(_doc_with_background(), html_path=tmp_path / "a.html")
    assert 'class="bg"' in out
    assert "data:image/png;base64," in out  # background inlined
    assert "color: transparent" in out  # invisible text layer
    assert "序言 Palantir" in out  # text preserved for selection/search
    assert 'data-w="' in out  # width hint for scaleX fitter


def test_html_image_writes_background_to_assets(tmp_path: Path) -> None:
    assets = tmp_path / "assets"
    out = render_html_image(
        _doc_with_background(), html_path=tmp_path / "a.html", assets_dir=assets
    )
    assert "assets/p1-page.png" in out
    assert (assets / "p1-page.png").read_bytes().startswith(b"\x89PNG")
