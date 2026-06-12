"""Intermediate representation shared by parser and renderers."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Union


BBox = tuple[float, float, float, float]


@dataclass
class Span:
    text: str
    font: str
    size: float
    color: str
    bold: bool
    italic: bool
    bbox: BBox
    origin: tuple[float, float] | None = None  # baseline origin (x, y) in pt


@dataclass
class Line:
    bbox: BBox
    spans: list[Span] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "".join(s.text for s in self.spans)


@dataclass
class TextBlock:
    bbox: BBox
    lines: list[Line] = field(default_factory=list)
    heading_level: int | None = None
    list_marker: Literal["bullet", "ordered", None] = None

    @property
    def text(self) -> str:
        return "\n".join(line.text for line in self.lines)


@dataclass
class TableBlock:
    bbox: BBox
    rows: list[list[str]] = field(default_factory=list)


@dataclass
class ImageBlock:
    bbox: BBox
    image_ref: str


Block = Union[TextBlock, TableBlock, ImageBlock]


@dataclass
class Page:
    index: int
    width: float
    height: float
    blocks: list[Block] = field(default_factory=list)
    background_ref: str | None = None


@dataclass
class FontResource:
    css_name: str
    family: str
    weight: int
    italic: bool
    woff2: bytes | None = None
    ascent: float = 0.0  # typo ascender / unitsPerEm (0 = unknown)
    advance: dict[int, float] = field(default_factory=dict)  # codepoint -> advance/upm


@dataclass
class ImageResource:
    ref: str
    ext: str
    data: bytes


@dataclass
class Document:
    pages: list[Page] = field(default_factory=list)
    fonts: dict[str, FontResource] = field(default_factory=dict)
    images: dict[str, ImageResource] = field(default_factory=dict)
    font_glyphmap: dict[str, dict[int, int]] = field(default_factory=dict)
