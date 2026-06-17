"""冒烟测试 — 不联网，mock LLM 调用。"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import fitz
import pytest

from pdf2md.output import safe_title
from pdf2md.render import parse_pages


# ── 端到端 mock 测试 ────────────────────────────────────────────


def _make_pdf(path: Path) -> None:
    """创建 1 页 PDF：含文字 + 嵌入 PNG。"""
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), "Hello World", fontsize=14)
    # 10x10 红色 PNG（含 alpha 通道 → 4 字节色值）
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 10, 10), 1)
    pix.clear_with(0xFF)
    pix.set_pixel(0, 0, (255, 0, 0, 255))
    page.insert_image(fitz.Rect(72, 200, 172, 300), stream=pix.tobytes("png"))
    pix = None
    doc.save(str(path))
    doc.close()


def _fake_transcribe(vision_cfg, png_bytes, page_no, total_pages, prev_tail, asset_names):
    img_ref = f"![图]({asset_names[0]})" if asset_names else ""
    return f"Hello World\n\n{img_ref}"


def _fake_refine(text_cfg, raw_text, page_no, total_pages, prev_md_tail, lang):
    return f"# Hello World\n\n{raw_text.strip()}"


@pytest.fixture()
def pdf_file(tmp_path: Path) -> Path:
    p = tmp_path / "sample.pdf"
    _make_pdf(p)
    return p


def test_convert_e2e(pdf_file: Path, tmp_path: Path):
    """mock LLM，验证 article.md + assets 正确生成。"""
    out = tmp_path / "out"

    with (
        patch("pdf2md.api.transcribe_page", side_effect=_fake_transcribe),
        patch("pdf2md.api.refine_page", side_effect=_fake_refine),
    ):
        from pdf2md.api import convert

        md_path = convert(
            pdf_file,
            out_dir=out,
            auth_token="fake",
            base_url="http://localhost:1",
        )

    assert md_path.exists()
    assert md_path.name == "article.md"

    text = md_path.read_text(encoding="utf-8")
    assert "title:" in text
    assert "# Hello World" in text

    assets = md_path.parent / "assets"
    if assets.exists():
        pngs = list(assets.glob("*.png"))
        assert len(pngs) >= 1
        # sha1[:16] 命名
        assert len(pngs[0].stem) == 16


def test_safe_title_strips_unsafe():
    assert safe_title('Test: "Hello" / World') == "Test Hello  World"


def test_safe_title_empty():
    assert safe_title("") == "untitled"


def test_safe_title_truncates():
    assert len(safe_title("a" * 200)) <= 120


def test_parse_pages_all():
    assert parse_pages(None, 5) == [0, 1, 2, 3, 4]


def test_parse_pages_range():
    assert parse_pages("1-3", 10) == [0, 1, 2]


def test_parse_pages_individual():
    assert parse_pages("2,5", 10) == [1, 4]


def test_parse_pages_reversed():
    assert parse_pages("3-1", 5) == [0, 1, 2]
