"""End-to-end check that embedded WOFF2 fonts get a usable Unicode cmap.

Embedded subset CID fonts in the sample PDF carry no Unicode cmap of their own;
without the rebuild step browsers fall back to a system font and CJK text renders
as tofu/overlapping glyphs. This test converts the preface page and asserts the
exported fonts can actually map the characters that appear there.
"""
from pathlib import Path

import pytest

from pdf2x.api import convert

_SAMPLE = Path(__file__).resolve().parent.parent / "examples" / "1.pdf"
_PREFACE_CPS = (0x5E8F, 0x8A00)  # 序 言


@pytest.mark.skipif(not _SAMPLE.exists(), reason="examples/1.pdf not available")
def test_preface_fonts_have_unicode_cmap(tmp_path: Path) -> None:
    fontTools_ttLib = pytest.importorskip("fontTools.ttLib")

    assets = tmp_path / "assets"
    convert(
        _SAMPLE,
        html=tmp_path / "1.html",
        mode="exact",
        assets_dir=assets,
        pages="5",
        ocr="off",
    )

    woff2_files = sorted(assets.glob("*.woff2"))
    assert woff2_files, "no WOFF2 fonts were exported"

    covered: set[int] = set()
    for path in woff2_files:
        tt = fontTools_ttLib.TTFont(path)
        best = tt.getBestCmap()
        if best:
            covered.update(best.keys())

    missing = [f"U+{cp:04X}" for cp in _PREFACE_CPS if cp not in covered]
    assert not missing, f"preface glyphs not in any font cmap: {missing}"
