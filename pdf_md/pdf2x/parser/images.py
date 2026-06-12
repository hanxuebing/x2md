"""Image extraction from PDF pages."""
from __future__ import annotations

from ..ir import ImageBlock, ImageResource


def extract_images(fpage, fitz_doc, images: dict[str, ImageResource]) -> list[ImageBlock]:
    out: list[ImageBlock] = []
    page_index = fpage.number
    for img_idx, info in enumerate(fpage.get_images(full=True)):
        xref = info[0]
        try:
            base = fitz_doc.extract_image(xref)
        except Exception:
            continue
        ext = base.get("ext", "png")
        data = base.get("image", b"")
        if not data:
            continue
        ref = f"p{page_index + 1}-img{img_idx + 1}.{ext}"

        bbox = (0.0, 0.0, 0.0, 0.0)
        for rect in fpage.get_image_rects(xref) or []:
            bbox = (rect.x0, rect.y0, rect.x1, rect.y1)
            break

        images[ref] = ImageResource(ref=ref, ext=ext, data=data)
        out.append(ImageBlock(bbox=bbox, image_ref=ref))
    return out
