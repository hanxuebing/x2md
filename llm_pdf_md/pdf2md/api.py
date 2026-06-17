"""公开 API：convert / convert_batch。

两阶段管线，逐页顺序处理（保持跨页上下文连续）：
  Stage 1 (vision): 多模态模型看页面图片 → 原始参考文章
  Stage 2 (text):   文本模型整理成人性化 Markdown
"""

from __future__ import annotations

import sys
from pathlib import Path

import fitz  # PyMuPDF

from pdf2md.config import Config, load_config
from pdf2md.llm import transcribe_page, refine_page
from pdf2md.output import doc_title, safe_title, write_article
from pdf2md.render import extract_page_images, parse_pages, render_page_png

_PREV_TAIL_LEN = 600  # 传入下一页的上下文末尾字符数


def convert(
    pdf: str | Path,
    *,
    md: str | Path | None = None,
    out_dir: str | Path | None = None,
    config: str | None = None,
    pages: str | None = None,
    quiet: bool = False,
    verbose: bool = False,
    **overrides,
) -> Path:
    """转换单个 PDF。

    - 给了 md → 单文件模式，assets 放在 md 同级 assets/
    - 否则 → 批量模式，输出到 out_dir/<安全标题>/
    返回输出的 article.md 路径。
    """
    cfg = load_config(config, **overrides)
    pdf_path = Path(pdf)
    doc = fitz.open(str(pdf_path))

    title = doc_title(doc.metadata or {}, pdf_path)

    if md:
        md_path = Path(md)
        dest_dir = md_path.parent
        assets_dir = dest_dir / "assets"
    else:
        base = Path(out_dir) if out_dir else Path("output")
        dest_dir = base / safe_title(title)
        assets_dir = dest_dir / "assets"

    dest_dir.mkdir(parents=True, exist_ok=True)

    page_indices = parse_pages(pages, len(doc))
    total = len(page_indices)

    parts: list[str] = []
    prev_raw_tail = ""  # Stage 1 上下文
    prev_md_tail = ""   # Stage 2 上下文

    for i, idx in enumerate(page_indices):
        page_no = i + 1
        page = doc[idx]

        if not quiet:
            print(f"  [{page_no}/{total}] 渲染第 {idx + 1} 页…", file=sys.stderr)

        # 抽取本页嵌入图片 → assets/
        asset_names = extract_page_images(page, doc, assets_dir)
        # 整页渲染为 PNG
        png_bytes = render_page_png(page, dpi=cfg.render.dpi)

        # Stage 1: 多模态模型 → 原始参考文章
        if not quiet:
            print(f"  [{page_no}/{total}] Stage 1: 多模态识别…", file=sys.stderr)
        raw_text = transcribe_page(
            vision_cfg=cfg.vision,
            png_bytes=png_bytes,
            page_no=page_no,
            total_pages=total,
            prev_tail=prev_raw_tail,
            asset_names=asset_names,
        )
        if verbose:
            print(f"    ── 原始转录 ({len(raw_text)} 字) ──", file=sys.stderr)

        # Stage 2: 文本模型 → 人性化 Markdown
        if not quiet:
            print(f"  [{page_no}/{total}] Stage 2: Markdown 排版…", file=sys.stderr)
        md_text = refine_page(
            text_cfg=cfg.text,
            raw_text=raw_text,
            page_no=page_no,
            total_pages=total,
            prev_md_tail=prev_md_tail,
            lang=cfg.output.lang,
        )

        parts.append(md_text)

        # 更新上下文尾部
        prev_raw_tail = raw_text[-_PREV_TAIL_LEN:] if raw_text else ""
        prev_md_tail = md_text[-_PREV_TAIL_LEN:] if md_text else ""

    doc.close()

    # 拼接
    sep = "\n\n---\n\n" if cfg.output.pagebreak else "\n\n"
    body = sep.join(parts)

    if md:
        result = write_article(dest_dir, title, body, pdf_path.name)
        # 单文件模式：如果用户指定了不同的文件名，重命名
        target = Path(md)
        if target != result:
            target.parent.mkdir(parents=True, exist_ok=True)
            result.rename(target)
            return target
        return result
    else:
        return write_article(dest_dir, title, body, pdf_path.name)


def convert_batch(
    inputs: list[str | Path],
    *,
    out_dir: str | Path = "output",
    recursive: bool = False,
    config: str | None = None,
    quiet: bool = False,
    verbose: bool = False,
    **overrides,
) -> list[Path]:
    """批量转换多个 PDF / 目录。

    每个 PDF 在 out_dir/ 下生成 <安全标题>/ 文件夹。
    多文件失败不互相影响；返回成功的输出路径列表。
    """
    pdfs = _collect_pdfs(inputs, recursive=recursive)

    if not pdfs:
        print("未找到任何 PDF 文件。", file=sys.stderr)
        return []

    results: list[Path] = []
    failed: list[tuple[Path, str]] = []

    for pdf_path in pdfs:
        if not quiet:
            print(f"\n处理: {pdf_path}", file=sys.stderr)
        try:
            result = convert(
                pdf_path,
                out_dir=out_dir,
                config=config,
                quiet=quiet,
                verbose=verbose,
                **overrides,
            )
            results.append(result)
        except Exception as exc:
            failed.append((pdf_path, str(exc)))
            print(f"  失败: {exc}", file=sys.stderr)

    if failed and not quiet:
        print(f"\n共 {len(failed)} 个文件失败：", file=sys.stderr)
        for p, err in failed:
            print(f"  {p}: {err}", file=sys.stderr)

    return results


def _collect_pdfs(
    inputs: list[str | Path], *, recursive: bool
) -> list[Path]:
    """展开输入列表中的目录，收集所有 .pdf 文件。"""
    pdfs: list[Path] = []
    for item in inputs:
        p = Path(item)
        if p.is_file() and p.suffix.lower() == ".pdf":
            pdfs.append(p)
        elif p.is_dir():
            pattern = "**/*.pdf" if recursive else "*.pdf"
            pdfs.extend(sorted(p.glob(pattern)))
        else:
            print(f"跳过不存在或非 PDF: {p}", file=sys.stderr)
    return pdfs
