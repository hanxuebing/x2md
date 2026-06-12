"""Top-level Python API used by both CLI and library callers."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Literal

from .ir import Document
from .parser import parse_pdf
from .render.html_exact import render_html_exact
from .render.html_flow import render_html_flow
from .render.html_image import render_html_image
from .render.markdown import render_markdown


OcrMode = Literal["auto", "always", "off"]
HtmlMode = Literal["exact", "flow", "image"]


def parse(
    pdf_path: str | Path,
    *,
    ocr: OcrMode = "auto",
    ocr_lang: str = "eng",
    pages: str | None = None,
    page_images: bool = False,
    page_image_dpi: int = 144,
    embed_fonts: bool = True,
    on_page: Callable[[int, int], None] | None = None,
) -> Document:
    """Parse a PDF into the internal Document IR.

    `on_page(done, total)` is invoked after each page is parsed, for progress.
    """
    return parse_pdf(
        Path(pdf_path),
        ocr=ocr,
        ocr_lang=ocr_lang,
        pages=pages,
        page_images=page_images,
        page_image_dpi=page_image_dpi,
        embed_fonts=embed_fonts,
        on_page=on_page,
    )


def convert(
    pdf_path: str | Path,
    *,
    html: str | Path | None = None,
    md: str | Path | None = None,
    mode: HtmlMode = "image",
    assets_dir: str | Path | None = None,
    ocr: OcrMode = "auto",
    ocr_lang: str = "eng",
    pages: str | None = None,
    page_image_dpi: int = 144,
    md_pagebreak: bool = False,
    on_page: Callable[[int, int], None] | None = None,
) -> Document:
    """Parse a PDF once and render to HTML and/or Markdown.

    At least one of `html` or `md` must be provided.
    `on_page(done, total)` is invoked after each page is parsed, for progress.
    """
    if html is None and md is None:
        raise ValueError("convert(): provide at least one of html=... or md=...")

    want_images = html is not None and mode == "image"
    doc = parse(
        pdf_path,
        ocr=ocr,
        ocr_lang=ocr_lang,
        pages=pages,
        page_images=want_images,
        page_image_dpi=page_image_dpi,
        embed_fonts=not want_images,
        on_page=on_page,
    )

    assets = Path(assets_dir) if assets_dir else None

    if html is not None:
        html_path = Path(html)
        renderers = {
            "exact": render_html_exact,
            "flow": render_html_flow,
            "image": render_html_image,
        }
        renderer = renderers[mode]
        html_text = renderer(doc, assets_dir=assets, html_path=html_path)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(html_text, encoding="utf-8")

    if md is not None:
        md_path = Path(md)
        md_text = render_markdown(
            doc,
            assets_dir=assets,
            md_path=md_path,
            pagebreak=md_pagebreak,
        )
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(md_text, encoding="utf-8")

    return doc


def collect_pdfs(
    inputs: Iterable[str | Path],
    *,
    recursive: bool = False,
) -> list[Path]:
    """Expand a mix of PDF files and directories into a deduped list of PDF paths.

    Directories are scanned for `*.pdf` (recursively when `recursive=True`).
    File paths are kept as-is. Order is preserved; duplicates (by resolved path)
    are dropped.
    """
    pattern = "**/*.pdf" if recursive else "*.pdf"
    pdfs: list[Path] = []
    seen: set[Path] = set()
    for item in inputs:
        p = Path(item)
        candidates = sorted(p.glob(pattern)) if p.is_dir() else [p]
        for c in candidates:
            key = c.resolve()
            if key not in seen:
                seen.add(key)
                pdfs.append(c)
    return pdfs


def convert_batch(
    inputs: Iterable[str | Path],
    *,
    out_dir: str | Path | None = None,
    mode: HtmlMode = "image",
    ocr: OcrMode = "auto",
    ocr_lang: str = "eng",
    pages: str | None = None,
    page_image_dpi: int = 144,
    md_pagebreak: bool = False,
    recursive: bool = False,
    on_done: Callable[[Path, Path], None] | None = None,
    on_page: Callable[[Path, int, int], None] | None = None,
) -> list[Path]:
    """Convert many PDFs, one output folder per file named after its stem.

    Each `<name>.pdf` produces `<out_dir>/<name>/` containing `<name>.html`,
    `<name>.md`, and an `assets/` directory for externalized images/fonts.
    `out_dir` defaults to the current directory. Returns the created folders.

    `on_done(pdf_path, folder)` is invoked after each file completes.
    `on_page(pdf_path, done, total)` is invoked per page within each file.
    Both are for progress reporting.
    """
    pdfs = collect_pdfs(inputs, recursive=recursive)
    if not pdfs:
        raise ValueError("convert_batch(): no PDF files found in inputs")

    root = Path(out_dir) if out_dir is not None else Path(".")
    folders: list[Path] = []
    for pdf in pdfs:
        folder = root / pdf.stem
        page_cb = (
            (lambda done, total, _pdf=pdf: on_page(_pdf, done, total))
            if on_page is not None
            else None
        )
        convert(
            pdf,
            html=folder / "article.html",
            md=folder / "article.md",
            mode=mode,
            assets_dir=folder / "assets",
            ocr=ocr,
            ocr_lang=ocr_lang,
            pages=pages,
            page_image_dpi=page_image_dpi,
            md_pagebreak=md_pagebreak,
            on_page=page_cb,
        )
        folders.append(folder)
        if on_done is not None:
            on_done(pdf, folder)
    return folders
