from __future__ import annotations

import hashlib
from pathlib import Path

import fitz  # PyMuPDF


def render_page_png(page: "fitz.Page", dpi: int = 150) -> bytes:
    """整页渲染为 PNG 字节，喂给多模态模型「看」。"""
    pix = page.get_pixmap(dpi=dpi)
    return pix.tobytes("png")


def _ext_for(image_ext: str) -> str:
    ext = (image_ext or "png").lower()
    if ext in ("jpe", "jpeg"):
        return "jpg"
    return ext


def extract_page_images(
    page: "fitz.Page", doc: "fitz.Document", assets_dir: Path
) -> list[str]:
    """抽取本页嵌入图片到 assets_dir，按 sha1(bytes)[:16] 命名（去重+幂等）。

    返回相对引用名列表，形如 ["assets/7f3a....png", ...]，供提示词告知模型。
    """
    names: list[str] = []
    seen: set[str] = set()
    for img in page.get_images(full=True):
        xref = img[0]
        try:
            extracted = doc.extract_image(xref)
        except Exception:
            continue
        data = extracted.get("image")
        if not data:
            continue
        digest = hashlib.sha1(data).hexdigest()[:16]
        if digest in seen:
            continue
        seen.add(digest)
        ext = _ext_for(extracted.get("ext", "png"))
        filename = f"{digest}.{ext}"
        assets_dir.mkdir(parents=True, exist_ok=True)
        target = assets_dir / filename
        if not target.exists():
            target.write_bytes(data)
        names.append(f"assets/{filename}")
    return names


def parse_pages(spec: str | None, page_count: int) -> list[int]:
    """解析 "1-5,8,12-15"（1 起始、含两端）为 0 起始页索引列表。

    spec 为空时返回全部页。
    """
    if not spec:
        return list(range(page_count))
    result: list[int] = []
    seen: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, _, b = part.partition("-")
            start = int(a)
            end = int(b)
        else:
            start = end = int(part)
        if start > end:
            start, end = end, start
        for n in range(start, end + 1):
            idx = n - 1
            if 0 <= idx < page_count and idx not in seen:
                seen.add(idx)
                result.append(idx)
    return result
