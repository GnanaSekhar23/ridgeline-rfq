"""Word (.docx) -> Doc, walking the body in document order so headings stay above their tables.

Row ids: <file>!P<n> paragraphs, <file>!T<t>R<r> table rows, <file>!H<n> header/footer text.
Tracked deletions (w:del) are dropped; struck-through runs are marked.
"""

from __future__ import annotations

from io import BytesIO

import docx
from docx.oxml.ns import qn
from PIL import Image

from rfq.config import MAX_TEXT_LINES
from rfq.extractors.common import row_text
from rfq.extractors.image import looks_like_logo, to_png
from rfq.models import Doc, ImagePart, Line

W_P, W_TBL, W_TR, W_TC, W_R, W_T, W_DEL = (
    qn("w:p"), qn("w:tbl"), qn("w:tr"), qn("w:tc"), qn("w:r"), qn("w:t"), qn("w:del")
)


def _is_struck(run) -> bool:
    rpr = run.find(qn("w:rPr"))
    if rpr is None:
        return False
    for tag in ("w:strike", "w:dstrike"):
        el = rpr.find(qn(tag))
        if el is not None and el.get(qn("w:val"), "true").lower() not in ("false", "0", "off"):
            return True
    return False


def _para_text(p) -> tuple[str, bool]:
    """Text of a paragraph (incl. tracked insertions, excl. deletions) and whether all of it is struck."""
    parts, struck_chars, total_chars = [], 0, 0
    for run in p.iter(W_R):
        if any(anc.tag == W_DEL for anc in run.iterancestors()):
            continue
        t = "".join(x.text or "" for x in run.iter(W_T))
        if not t:
            continue
        parts.append(t)
        n = len(t.strip())
        total_chars += n
        if _is_struck(run):
            struck_chars += n
    text = " ".join("".join(parts).split())
    return text, bool(total_chars) and struck_chars == total_chars


def _style(p, d) -> str | None:
    ppr = p.find(qn("w:pPr"))
    if ppr is None:
        return None
    ps = ppr.find(qn("w:pStyle"))
    if ps is None:
        return None
    sid = ps.get(qn("w:val"))
    try:
        return d.styles.get_by_id(sid, 1).name if sid else None  # 1 = WD_STYLE_TYPE.PARAGRAPH
    except Exception:
        return sid


def _pictures(name: str, d, doc: Doc) -> None:
    """Embedded pictures in the body, in document order (a pasted photo or scan of a list).
    Banner-shaped logos are skipped; pictures Pillow can't read (EMF/WMF) are noted as lost."""
    seen: set[str] = set()
    n = 0
    for blip in d.element.body.iter(qn("a:blip")):
        rid = blip.get(qn("r:embed"))
        if not rid or rid in seen or rid not in d.part.rels:
            continue
        seen.add(rid)
        rel = d.part.rels[rid]
        if rel.is_external:
            continue
        blob = rel.target_part.blob
        n += 1
        label = f"{name} picture {n}"
        try:
            img = Image.open(BytesIO(blob))
            img.load()
        except Exception:
            doc.truncated = True
            doc.notes.append(f"{label}: picture format could not be read; not sent")
            continue
        if looks_like_logo(*img.size):
            doc.notes.append(f"{label}: {img.width}x{img.height} looks like a logo; not sent")
            continue
        png, w, h = to_png(img)
        doc.images.append(ImagePart(label=label, png=png, width=w, height=h))
    if doc.images:
        doc.notes.append(f"{len(doc.images)} embedded picture(s) sent as images")


def extract_docx(name: str, data: bytes) -> Doc:
    doc = Doc(source=name, kind="docx")
    d = docx.Document(BytesIO(data))
    n_p = n_t = 0
    for block in d.element.body.iterchildren():
        if block.tag == W_P:
            text, struck = _para_text(block)
            if text:
                n_p += 1
                style = _style(block, d)
                doc.lines.append(Line(row_id=f"{name}!P{n_p}", text=text, struck=struck,
                                      style=style if style and style != "Normal" else None))
        elif block.tag == W_TBL:
            n_t += 1
            for r_idx, tr in enumerate(block.iter(W_TR), start=1):
                cells, struck_flags = [], []
                for tc in tr.findall(W_TC):
                    paras = [_para_text(p) for p in tc.iter(W_P)]
                    cells.append(" ".join(t for t, _ in paras if t))
                    struck_flags.append(bool(paras) and all(s for t, s in paras if t) and any(t for t, _ in paras))
                if not any(cells):
                    continue
                filled = [(c, s) for c, s in zip(cells, struck_flags) if c]
                whole = all(s for _, s in filled)
                some = any(s for _, s in filled)
                doc.lines.append(Line(
                    row_id=f"{name}!T{n_t}R{r_idx}", text=row_text(cells), cells=cells, struck=whole,
                    note="some cells struck" if some and not whole else None,
                ))
        if len(doc.lines) > MAX_TEXT_LINES:
            doc.truncated = True
            doc.notes.append(f"truncated at {MAX_TEXT_LINES} lines")
            break
    _pictures(name, d, doc)
    n_h = 0
    for sec in d.sections:
        for part in (sec.header, sec.footer):
            for p in part.paragraphs:
                text = " ".join(p.text.split())
                if text:
                    n_h += 1
                    doc.lines.append(Line(row_id=f"{name}!H{n_h}", text=text, style="header/footer"))
    return doc
