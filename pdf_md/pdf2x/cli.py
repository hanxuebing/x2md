"""CLI entry point: `pdf2x INPUT [INPUT ...] [OPTIONS]`."""
from __future__ import annotations

import sys
from pathlib import Path

import click

from . import __version__
from .api import collect_pdfs, convert, convert_batch


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument(
    "inputs",
    nargs=-1,
    required=True,
    type=click.Path(exists=True, path_type=Path),
)
@click.option("--html", "html_out", type=click.Path(path_type=Path), help="Output HTML path (single-file mode only).")
@click.option("--md", "md_out", type=click.Path(path_type=Path), help="Output Markdown path (single-file mode only).")
@click.option(
    "--out-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Batch mode: write one folder per PDF (named after the file) under this directory. Defaults to the current directory.",
)
@click.option(
    "-r",
    "--recursive",
    is_flag=True,
    help="Recurse into subdirectories when an input is a directory.",
)
@click.option(
    "--mode",
    type=click.Choice(["exact", "flow", "image"]),
    default="image",
    show_default=True,
    help="HTML rendering mode.",
)
@click.option(
    "--dpi",
    type=int,
    default=144,
    show_default=True,
    help="DPI for page images in 'image' mode (higher = sharper but bigger).",
)
@click.option(
    "--assets-dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Single-file mode: directory for external images/fonts; if omitted, assets are inlined.",
)
@click.option(
    "--ocr",
    type=click.Choice(["auto", "always", "off"]),
    default="auto",
    show_default=True,
    help="OCR strategy.",
)
@click.option("--ocr-lang", default="eng", show_default=True, help="Tesseract language code.")
@click.option("--pages", default=None, help='Page range, e.g. "1-5,8".')
@click.option("--md-pagebreak", is_flag=True, help="Insert `---` between pages in Markdown.")
@click.option("-q", "--quiet", is_flag=True, help="Suppress progress messages.")
@click.option("-v", "--verbose", is_flag=True, help="Verbose progress messages.")
@click.version_option(__version__, prog_name="pdf2x")
def main(
    inputs: tuple[Path, ...],
    html_out: Path | None,
    md_out: Path | None,
    out_dir: Path | None,
    recursive: bool,
    mode: str,
    dpi: int,
    assets_dir: Path | None,
    ocr: str,
    ocr_lang: str,
    pages: str | None,
    md_pagebreak: bool,
    quiet: bool,
    verbose: bool,
) -> None:
    """Convert one or more PDFs to HTML and/or Markdown.

    Single-file mode: pass one PDF plus --html/--md to control exact output paths.

    Batch mode (multiple inputs, a directory, or --out-dir): each PDF gets its own
    folder named after the file, containing <name>.html, <name>.md, and assets/.
    """
    def log(msg: str) -> None:
        if not quiet:
            click.echo(msg, err=True)

    legacy = (
        len(inputs) == 1
        and inputs[0].is_file()
        and out_dir is None
        and not recursive
        and (html_out is not None or md_out is not None)
    )

    def page_progress(done: int, total: int) -> None:
        if quiet:
            return
        end = done >= total
        click.echo(f"\r  page {done}/{total}" + (" " * 8), err=True, nl=end)

    if legacy:
        (src,) = inputs
        if verbose:
            log(f"pdf2x {__version__}: parsing {src}")
        try:
            convert(
                src,
                html=html_out,
                md=md_out,
                mode=mode,  # type: ignore[arg-type]
                assets_dir=assets_dir,
                ocr=ocr,  # type: ignore[arg-type]
                ocr_lang=ocr_lang,
                pages=pages,
                page_image_dpi=dpi,
                md_pagebreak=md_pagebreak,
                on_page=page_progress,
            )
        except Exception as exc:  # noqa: BLE001
            click.echo(f"error: {exc}", err=True)
            sys.exit(1)
        if html_out:
            log(f"wrote {html_out}")
        if md_out:
            log(f"wrote {md_out}")
        return

    # Batch mode.
    if html_out is not None or md_out is not None or assets_dir is not None:
        click.echo(
            "error: --html/--md/--assets-dir only apply to single-file mode; "
            "use --out-dir for batch output",
            err=True,
        )
        sys.exit(2)

    pdfs = collect_pdfs(inputs, recursive=recursive)
    if not pdfs:
        click.echo("error: no PDF files found in inputs", err=True)
        sys.exit(1)

    n_files = len(pdfs)
    file_index = {p.resolve(): i for i, p in enumerate(pdfs, 1)}
    log(f"pdf2x {__version__}: batch converting {n_files} file(s)")

    def batch_page(pdf: Path, done: int, total: int) -> None:
        if quiet:
            return
        i = file_index.get(pdf.resolve(), 0)
        end = done >= total
        click.echo(
            f"\r  [{i}/{n_files}] {pdf.name}: page {done}/{total}" + (" " * 8),
            err=True,
            nl=end,
        )

    try:
        folders = convert_batch(
            list(inputs),
            out_dir=out_dir,
            mode=mode,  # type: ignore[arg-type]
            ocr=ocr,  # type: ignore[arg-type]
            ocr_lang=ocr_lang,
            pages=pages,
            page_image_dpi=dpi,
            md_pagebreak=md_pagebreak,
            recursive=recursive,
            on_page=batch_page,
            on_done=lambda pdf, folder: log(f"  -> {folder}/"),
        )
    except Exception as exc:  # noqa: BLE001
        click.echo(f"error: {exc}", err=True)
        sys.exit(1)

    log(f"done: {len(folders)} file(s)")


if __name__ == "__main__":
    main()
