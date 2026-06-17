"""输出工具：安全标题、YAML frontmatter、写 article.md。

遵循 x2md 导出标准：
  output/<安全标题>/article.md  (带 YAML frontmatter)
  output/<安全标题>/assets/     (图片资源，sha1 命名)
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path


_UNSAFE_CHARS = re.compile(r'[\\/:*?"<>|]')


def safe_title(raw: str, max_len: int = 120) -> str:
    """把标题转为安全目录名：剔除非法字符、去首尾空白、截断。"""
    s = _UNSAFE_CHARS.sub("", raw).strip()
    if not s:
        s = "untitled"
    return s[:max_len]


def doc_title(metadata: dict, pdf_path: Path) -> str:
    """取 PDF 元数据 title，没有则用文件名 stem。"""
    title = (metadata.get("title") or "").strip()
    if title:
        return title
    return pdf_path.stem


def write_article(
    out_dir: Path,
    title: str,
    body: str,
    source: str,
) -> Path:
    """写 article.md（带 YAML frontmatter）到 out_dir。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    frontmatter = (
        "---\n"
        f'title: "{title}"\n'
        f"date: \"{date.today().isoformat()}\"\n"
        f'source: "{source}"\n'
        f'generator: "pdf2md (multimodal LLM)"\n'
        "---\n\n"
    )
    md_path = out_dir / "article.md"
    md_path.write_text(frontmatter + body, encoding="utf-8")
    return md_path
