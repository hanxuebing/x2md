"""pdf2x — convert PDF to pixel-faithful HTML and structure-aligned Markdown."""
from __future__ import annotations

from .api import collect_pdfs, convert, convert_batch, parse
from .ir import (
    Document,
    Page,
    TextBlock,
    TableBlock,
    ImageBlock,
    Line,
    Span,
    FontResource,
    ImageResource,
)

__all__ = [
    "convert",
    "convert_batch",
    "collect_pdfs",
    "parse",
    "Document",
    "Page",
    "TextBlock",
    "TableBlock",
    "ImageBlock",
    "Line",
    "Span",
    "FontResource",
    "ImageResource",
]

__version__ = "0.1.0"
