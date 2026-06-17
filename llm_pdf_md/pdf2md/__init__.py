"""pdf2md — 多模态大模型 PDF → 人性化 Markdown 转换器。

公开 API:
    convert(pdf, ...) -> Path
    convert_batch(inputs, ...) -> list[Path]
"""

from pdf2md.api import convert, convert_batch

__all__ = ["convert", "convert_batch"]
__version__ = "0.1.0"
