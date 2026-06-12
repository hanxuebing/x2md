"""Structure-aligned Markdown renderer."""
from __future__ import annotations

import re
from pathlib import Path

from ..ir import Document, ImageBlock, ImageResource, Line, TableBlock, TextBlock


_BULLET_RE = re.compile(r"^\s*([•·●○▪◦\-–—*])\s+")
_ORDERED_RE = re.compile(r"^\s*(\d+)[.)、]\s+")


def render_markdown(
    doc: Document,
    *,
    md_path: Path,
    assets_dir: Path | None = None,
    pagebreak: bool = False,
) -> str:
    """Return a Markdown string whose structure mirrors the PDF reading order."""
    assets_path = _resolve_assets_dir(md_path, assets_dir, doc.images)
    if assets_path is not None:
        assets_path.mkdir(parents=True, exist_ok=True)

    parts: list[str] = []
    for page_idx, page in enumerate(doc.pages):
        if pagebreak and page_idx > 0:
            parts.append("\n\n---\n\n")
        for block in page.blocks:
            if isinstance(block, TextBlock):
                parts.append(_render_text(block))
            elif isinstance(block, TableBlock):
                parts.append(_render_table(block))
            elif isinstance(block, ImageBlock):
                parts.append(_render_image(block, doc, md_path, assets_path))
            parts.append("\n\n")
    text = "".join(parts)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def _resolve_assets_dir(
    md_path: Path, assets_dir: Path | None, images: dict
) -> Path | None:
    if assets_dir is not None:
        return Path(assets_dir)
    if not images:
        return None
    return md_path.parent / f"{md_path.stem}_assets"


def _render_text(block: TextBlock) -> str:
    if not block.lines:
        return ""
    if block.heading_level:
        level = max(1, min(6, block.heading_level))
        hashes = "#" * level
        text = " ".join(_inline_text(line) for line in block.lines).strip()
        return f"{hashes} {text}"

    line_texts: list[str] = []
    list_mode: str | None = None
    for line in block.lines:
        raw = line.text
        bullet_m = _BULLET_RE.match(raw)
        ordered_m = _ORDERED_RE.match(raw)
        if bullet_m:
            line_texts.append(f"- {_inline_text(line, strip_chars=bullet_m.end())}")
            list_mode = "ul"
        elif ordered_m:
            line_texts.append(
                f"{ordered_m.group(1)}. {_inline_text(line, strip_chars=ordered_m.end())}"
            )
            list_mode = "ol"
        else:
            line_texts.append(_inline_text(line))

    if list_mode is not None:
        return "\n".join(line_texts)
    return " ".join(t.strip() for t in line_texts if t.strip())


def _inline_text(line: Line, *, strip_chars: int = 0) -> str:
    # Merge consecutive spans sharing the same (bold, italic) style so each run
    # gets a single pair of markers — avoids `**a****b**` from PyMuPDF splitting
    # a styled word across spans.
    runs: list[list] = []  # [text, bold, italic]
    consumed = 0
    for sp in line.spans:
        text = sp.text
        if strip_chars > consumed:
            cut = min(strip_chars - consumed, len(text))
            consumed += cut
            text = text[cut:]
        if not text:
            continue
        if runs and runs[-1][1] == sp.bold and runs[-1][2] == sp.italic:
            runs[-1][0] += text
        else:
            runs.append([text, sp.bold, sp.italic])

    out: list[str] = []
    for text, bold, italic in runs:
        if not (bold or italic):
            out.append(text)
            continue
        # A whitespace-only styled run carries inter-word spacing — emit it bare,
        # never wrapped, so we don't produce `** **`.
        if not text.strip():
            out.append(text)
            continue
        marker = "***" if bold and italic else "**" if bold else "*"
        # Keep leading/trailing whitespace outside the markers; CommonMark
        # emphasis cannot start or end with a space.
        lead = text[: len(text) - len(text.lstrip())]
        trail = text[len(text.rstrip()) :]
        core = text[len(lead) : len(text) - len(trail)]
        out.append(f"{lead}{marker}{core}{marker}{trail}")
    return "".join(out)


def _render_table(block: TableBlock) -> str:
    if not block.rows:
        return ""
    width = max(len(r) for r in block.rows)
    rows_norm = [list(r) + [""] * (width - len(r)) for r in block.rows]
    out = []
    out.append("| " + " | ".join(_md_cell(c) for c in rows_norm[0]) + " |")
    out.append("| " + " | ".join("---" for _ in range(width)) + " |")
    for row in rows_norm[1:]:
        out.append("| " + " | ".join(_md_cell(c) for c in row) + " |")
    return "\n".join(out)


def _md_cell(text: str) -> str:
    return (text or "").replace("|", "\\|").replace("\n", " ").strip()


def _render_image(
    block: ImageBlock,
    doc: Document,
    md_path: Path,
    assets_path: Path | None,
) -> str:
    res = doc.images.get(block.image_ref)
    if res is None or assets_path is None:
        return ""
    _write_asset(assets_path, res)
    try:
        rel = assets_path.resolve().relative_to(md_path.resolve().parent).as_posix()
    except ValueError:
        rel = assets_path.name
    return f"![]({rel}/{res.ref})"


def _write_asset(assets_path: Path, res: ImageResource) -> None:
    (assets_path / res.ref).write_bytes(res.data)
