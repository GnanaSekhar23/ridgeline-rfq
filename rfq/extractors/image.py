"""Images (photos, scans, pasted screenshots) -> Doc with one PNG for the model.

Inline banner-shaped images (logos, signature graphics) are skipped and noted, so we don't pay
to send them and the model isn't tempted to read a company name as an item.
"""

from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps

from rfq.config import LOGO_MAX_HEIGHT_PX, LOGO_MAX_SIDE_PX, LOGO_MIN_ASPECT, MAX_IMAGE_SIDE_PX
from rfq.models import Doc, ImagePart


def to_png(img: Image.Image) -> tuple[bytes, int, int]:
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.thumbnail((MAX_IMAGE_SIDE_PX, MAX_IMAGE_SIDE_PX))
    buf = BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue(), img.width, img.height


def looks_like_logo(w: int, h: int) -> bool:
    if min(w, h) < LOGO_MAX_SIDE_PX and max(w, h) < 2 * LOGO_MAX_SIDE_PX:
        return True  # small icon
    return h <= LOGO_MAX_HEIGHT_PX and w / max(h, 1) >= LOGO_MIN_ASPECT  # wide banner


def extract_image(name: str, data: bytes, inline: bool = False, alt: str = "") -> Doc:
    doc = Doc(source=name, kind="image")
    if alt:
        doc.notes.append(f"alt text: {alt!r}")
    img = Image.open(BytesIO(data))
    img.load()
    w, h = img.size
    if inline and looks_like_logo(w, h):
        doc.skipped = True
        doc.notes.append(f"inline {w}x{h} image looks like a logo/signature; not sent to the model")
        return doc
    png, pw, ph = to_png(img)
    doc.images.append(ImagePart(label=name, png=png, width=pw, height=ph))
    return doc
