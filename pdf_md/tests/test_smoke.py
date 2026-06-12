from pathlib import Path

from pdf2x.ir import (
    Document,
    ImageBlock,
    ImageResource,
    Line,
    Page,
    Span,
    TableBlock,
    TextBlock,
)
from pdf2x.render.html_exact import render_html_exact
from pdf2x.render.html_flow import render_html_flow
from pdf2x.render.html_image import render_html_image
from pdf2x.render.markdown import render_markdown


def _doc_with_heading() -> Document:
    span = Span(
        text="Hello world",
        font="TestFont",
        size=18.0,
        color="#000000",
        bold=True,
        italic=False,
        bbox=(72.0, 72.0, 200.0, 90.0),
    )
    line = Line(bbox=(72.0, 72.0, 200.0, 90.0), spans=[span])
    block = TextBlock(
        bbox=(72.0, 72.0, 200.0, 90.0), lines=[line], heading_level=1
    )
    page = Page(index=0, width=612.0, height=792.0, blocks=[block])
    return Document(pages=[page])


def _doc_with_table() -> Document:
    table = TableBlock(
        bbox=(72.0, 200.0, 540.0, 300.0),
        rows=[["Col A", "Col B"], ["1", "2"]],
    )
    page = Page(index=0, width=612.0, height=792.0, blocks=[table])
    return Document(pages=[page])


def _doc_with_image() -> Document:
    img_block = ImageBlock(bbox=(72.0, 100.0, 300.0, 250.0), image_ref="p1-img1.png")
    page = Page(index=0, width=612.0, height=792.0, blocks=[img_block])
    doc = Document(pages=[page])
    doc.images["p1-img1.png"] = ImageResource(
        ref="p1-img1.png", ext="png", data=b"\x89PNG\r\n\x1a\n"
    )
    return doc


def test_markdown_heading(tmp_path: Path) -> None:
    out = render_markdown(_doc_with_heading(), md_path=tmp_path / "a.md")
    assert out.startswith("# Hello world")


def test_markdown_table(tmp_path: Path) -> None:
    out = render_markdown(_doc_with_table(), md_path=tmp_path / "a.md")
    assert "| Col A | Col B |" in out
    assert "| --- | --- |" in out
    assert "| 1 | 2 |" in out


def test_markdown_image_default_assets_dir(tmp_path: Path) -> None:
    md_path = tmp_path / "doc.md"
    out = render_markdown(_doc_with_image(), md_path=md_path)
    assert "(doc_assets/p1-img1.png)" in out
    assert (tmp_path / "doc_assets" / "p1-img1.png").read_bytes().startswith(b"\x89PNG")


def test_html_exact_positions_span(tmp_path: Path) -> None:
    out = render_html_exact(_doc_with_heading(), html_path=tmp_path / "a.html")
    assert "Hello world" in out
    assert "left:72.00pt" in out
    assert "position: relative" in out


def test_html_flow_uses_semantic_heading(tmp_path: Path) -> None:
    out = render_html_flow(_doc_with_heading(), html_path=tmp_path / "a.html")
    assert "<h1>" in out
    assert "Hello world" in out


def test_html_exact_inlines_image(tmp_path: Path) -> None:
    out = render_html_exact(_doc_with_image(), html_path=tmp_path / "a.html")
    assert "data:image/png;base64," in out


def _doc_with_page_image() -> Document:
    span = Span(
        text="序言",
        font="F1",
        size=36.0,
        color="#000000",
        bold=True,
        italic=False,
        bbox=(485.28, 141.84, 521.28, 177.84),
    )
    line = Line(bbox=(485.28, 141.84, 521.28, 177.84), spans=[span])
    block = TextBlock(bbox=(485.28, 141.84, 521.28, 177.84), lines=[line])
    page = Page(
        index=0,
        width=595.30,
        height=841.90,
        blocks=[block],
        background_ref="p1-page.png",
    )
    doc = Document(pages=[page])
    doc.images["p1-page.png"] = ImageResource(
        ref="p1-page.png", ext="png", data=b"\x89PNG\r\n\x1a\n"
    )
    return doc


def test_html_image_background_and_text_layer(tmp_path: Path) -> None:
    doc = _doc_with_page_image()
    out = render_html_image(
        doc, html_path=tmp_path / "a.html", assets_dir=tmp_path / "assets"
    )
    assert 'class="bg"' in out
    assert "序言" in out
    assert "data-w=" in out
    assert "color: transparent" in out
    assert (tmp_path / "assets" / "p1-page.png").read_bytes().startswith(b"\x89PNG")


def test_html_image_inlines_background(tmp_path: Path) -> None:
    out = render_html_image(_doc_with_page_image(), html_path=tmp_path / "a.html")
    assert "data:image/png;base64," in out
