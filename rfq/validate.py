"""Model answer -> Result. Code, not the model, owns the facts it can check.

Step-6 scope: resolve row ids against the real extracted lines (raw from the source text,
qty/uom from table cells under a Qty/UOM header), drop unknown / struck / not-allowed quoted
rows, map image lines to their source file, apply the multi-sheet rule, assemble needs_review.
Code rules over the model's answer: a non-request keeps no lines and no review flag; a request
with read problems, a truncated prompt, an unclear multi-sheet workbook, a list at the item cap,
or no lines at all is forced to needs_review.
Step 7 adds deeper checks (grounding of descriptions, qty-is-not-a-size, coverage).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from rapidfuzz import fuzz

from rfq.config import MAX_LINE_ITEMS, REQUEST_KINDS
from rfq.matcher import match_line
from rfq.models import Doc, Email, Line, LineItem, Result

log = logging.getLogger(__name__)

UOM_WORDS = {
    "EA": ("ea", "each", "pc", "pcs", "piece", "pieces", "jt", "jts", "joint", "joints", "length",
           "lengths", "lg", "lgs", "lgth", "lgths", "no", "nos", "qty", "unit", "units"),
    "FT": ("ft", "feet", "foot", "lf", "'"),
    "M": ("m", "meter", "meters", "metre", "metres"),
    "IN": ("in", "inch", "inches"),
    "BX": ("bx", "box", "boxes"),
    "PK": ("pk", "pack", "packs", "pkg", "pkgs"),
    "PR": ("pr", "pair", "pairs"),
    "DZ": ("dz", "doz", "dozen"),
    "RL": ("rl", "roll", "rolls"),
    "LB": ("lb", "lbs", "pound", "pounds"),
    "SET": ("set", "sets"),
    "GAL": ("gal", "gals", "gallon", "gallons"),
    "BAG": ("bag", "bags"),
    "CS": ("cs", "case", "cases"),
}
_UOM_LOOKUP = {w: code for code, words in UOM_WORDS.items() for w in words}
_QTY_HEADER = re.compile(r"^(qty|qty\.|quantity|quan|q'?ty|qnty|no\.? ?req'?d|req'?d qty|order qty)$", re.I)
_UOM_HEADER = re.compile(r"^(uom|u/m|u\.o\.m\.?|unit|units|um)$", re.I)
_QTY_CELL = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*([a-z'.]*)\s*$", re.I)


def normalize_uom(word: str | None) -> str | None:
    if not word:
        return None
    w = word.strip().lower().rstrip(".")
    if w.upper() in UOM_WORDS:
        return w.upper()
    return _UOM_LOOKUP.get(w)


def _num(x: float | None) -> float | int | None:
    if x is None:
        return None
    return int(x) if float(x).is_integer() else float(x)


# ---------------------------------------------------------------- source index
@dataclass
class _Row:
    line: Line
    doc: Doc
    index: int  # position in doc.lines


@dataclass
class SourceIndex:
    rows: dict[str, _Row] = field(default_factory=dict)
    image_sources: dict[str, str] = field(default_factory=dict)  # image label -> doc source

    @classmethod
    def build(cls, docs: list[Doc]) -> "SourceIndex":
        idx = cls()
        for d in docs:
            for i, ln in enumerate(d.lines):
                idx.rows.setdefault(ln.row_id, _Row(ln, d, i))
            for im in d.images:
                idx.image_sources[im.label] = d.source
        return idx


def _table_key(row_id: str) -> str:
    """Lines of the same table share everything before the final !R<n> / R<n>."""
    return re.sub(r"R\d+$", "", row_id)


def _header_columns(row: _Row) -> tuple[int | None, int | None]:
    """Find the nearest header row above this table row: (qty col, uom col)."""
    key = _table_key(row.line.row_id)
    for prev in reversed(row.doc.lines[: row.index]):
        if not prev.cells or _table_key(prev.row_id) != key:
            continue
        cells = [c.strip() for c in prev.cells]
        q = next((i for i, c in enumerate(cells) if _QTY_HEADER.match(c)), None)
        if q is not None:
            u = next((i for i, c in enumerate(cells) if _UOM_HEADER.match(c)), None)
            return q, u
    return None, None


def qty_uom_from_cells(row: _Row) -> tuple[float | None, str | None, bool]:
    """(qty, uom, found) from the row's own cells, using the table's header."""
    cells = row.line.cells
    if not cells:
        return None, None, False
    q_col, u_col = _header_columns(row)
    if q_col is None or q_col >= len(cells):
        return None, None, False
    m = _QTY_CELL.match(cells[q_col])
    if not m:
        return None, None, False
    qty = float(m.group(1).replace(",", "."))
    uom = None
    if u_col is not None and u_col < len(cells):
        uom = normalize_uom(cells[u_col])
    if uom is None and m.group(2):
        uom = normalize_uom(m.group(2))
    return qty, uom, True


def _norm(s: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9/\"'.#-]+", " ", s.lower()).split())


def grounded_fragment(model_raw: str, line_text: str) -> bool:
    """Is the model's raw a piece of the real line (so we may keep the fragment)?"""
    a, b = _norm(model_raw), _norm(line_text)
    if not a:
        return False
    return a in b or fuzz.partial_ratio(a, b) >= 90


# ---------------------------------------------------------------- scanned-row numbering check
_ITEM_NO = re.compile(r"^\s*(?:item\s*)?#?\s*(\d{1,4})\s*(?:[|.):\-]|\s)", re.I)


def numbering_problem(raws: list[str]) -> str | None:
    """Item numbers read from an image should run 1, 2, 3 ... A skip or repeat means a row was
    probably dropped, doubled or read from the wrong line. Only applies when the leading numbers
    really are an item sequence (not, say, quantities at the start of each line). Numbering that
    restarts at 1 (a new section) is fine."""
    nums = [int(m.group(1)) for r in raws if (m := _ITEM_NO.match(r))]
    if len(nums) < 3 or len(nums) < 0.8 * len(raws):
        return None
    steps = [b - a for a, b in zip(nums, nums[1:])]
    if sum(1 for s in steps if s == 1) < 0.6 * len(steps):
        return None  # leading numbers don't form a sequence: not item numbers
    issues: list[str] = []
    segment: list[int] = []
    for n in nums + [1]:  # sentinel restart flushes the last segment
        if segment and n == 1:
            seen = set()
            for a, b in zip(segment, segment[1:]):
                if b == a or b in seen:
                    issues.append(f"{b} repeated")
                elif b > a + 1:
                    issues.append(f"{a + 1}-{b - 1} missing" if b > a + 2 else f"{a + 1} missing")
                elif b < a:
                    issues.append(f"{b} after {a}")
                seen.add(a)
            segment = []
        segment.append(n)
    return ", ".join(dict.fromkeys(issues)) or None


# ---------------------------------------------------------------- assembly
def _sheet_of(row_id: str) -> tuple[str, str] | None:
    parts = row_id.split("!")
    return (parts[0], parts[1]) if len(parts) == 3 else None


def build_result(
    email: Email,
    docs: list[Doc],
    extraction,
    *,
    parent: str | None = None,
    problems: list[str] | None = None,
    model_error: str | None = None,
    prompt_truncated: bool = False,
) -> Result:
    problems = list(problems or [])
    if extraction is None:
        reason = "; ".join([model_error or "no model answer"] + problems)
        return Result(classification="rfq", needs_review=True, review_reason=reason)

    ans = extraction
    kind = ans.classification
    if kind not in REQUEST_KINDS:
        # Non-requests carry no lines and no review flag (README). The model may say otherwise;
        # code has the last word, and we log what we threw away so it can be checked.
        if ans.line_items:
            log.warning("%s: %s answer had %d line(s); dropped", email.id, kind, len(ans.line_items))
        if ans.needs_review:
            log.info("%s: needs_review on a %s dropped (%s)", email.id, kind, ans.review_reason)
        return Result(classification=kind)

    idx = SourceIndex.build(docs)
    image_docs = [d.source for d in docs if d.images]
    reasons: list[str] = []
    if ans.needs_review:
        reasons.append(ans.review_reason or "model flagged for review")
    reasons += problems
    if prompt_truncated:
        reasons.append("email too long: only part of it was read")

    versions = {}  # workbook -> sheets to keep
    for sd in ans.sheet_decisions:
        if sd.relation == "unclear":
            reasons.append(f"{sd.file}: cannot tell whether the sheets are sections or versions ({sd.why})")
        elif sd.relation == "versions":
            versions[sd.file] = set(sd.sheets_used)

    items: list[LineItem] = []
    seen: set[tuple] = set()
    dropped: list[str] = []
    image_raws: dict[str, list[str]] = {}  # source -> raws read from its images, in answer order
    if len(ans.line_items) >= MAX_LINE_ITEMS:
        reasons.append(f"list reached the {MAX_LINE_ITEMS}-item limit of one model answer; it may be longer")
    for lo in ans.line_items:
        if lo.row_id:
            row = idx.rows.get(lo.row_id)
            if row is None:
                dropped.append(f"unknown row {lo.row_id}")
                continue
            if row.line.struck:
                dropped.append(f"struck row {lo.row_id}")
                continue
            if lo.row_id.startswith("body!Q") and kind == "rfq":
                dropped.append(f"quoted row {lo.row_id} in an rfq")
                continue
            sheet = _sheet_of(lo.row_id)
            if sheet and sheet[0] in versions and sheet[1] not in versions[sheet[0]]:
                dropped.append(f"row {lo.row_id} from a superseded sheet")
                continue
            line = row.line
            if line.cells:
                raw = line.text  # a table row: its cells on one line
            else:
                raw = lo.raw if grounded_fragment(lo.raw, line.text) else line.text
            qty, uom = lo.qty, lo.uom
            c_qty, c_uom, found = qty_uom_from_cells(row)
            if found:
                qty, uom = c_qty, (c_uom or uom)
            source = row.doc.source
        elif lo.image:
            source = idx.image_sources.get(lo.image)
            if source is None:
                source = image_docs[0] if len(image_docs) == 1 else None
            if source is None:
                dropped.append(f"unknown image {lo.image!r}")
                continue
            raw, qty, uom = lo.raw, lo.qty, lo.uom
            image_raws.setdefault(source, []).append(raw)
        else:
            dropped.append("line with neither row id nor image")
            continue
        if not raw.strip() or not lo.description.strip():
            dropped.append(f"empty line {lo.row_id or lo.image}")
            continue
        sig = (source, raw, lo.description, qty)
        if sig in seen:
            continue
        seen.add(sig)
        li = LineItem(raw=raw.strip(), description=lo.description.strip(), qty=_num(qty),
                      uom=normalize_uom(uom) if uom else None, source=source)
        attrs = getattr(lo, "attrs", None)  # present only when the matcher is enabled
        if attrs is not None:
            m = match_line(attrs, f"{lo.description} {raw}")
            li.sku, li.match, li.match_reason, li.candidates = m.sku, m.match, m.reason, m.candidates or None
        items.append(li)
    if dropped:
        log.info("%s: dropped %d model line(s): %s", email.id, len(dropped), "; ".join(dropped[:10]))
    for src, raws in image_raws.items():
        issue = numbering_problem(raws)
        if issue:
            reasons.append(f"{src}: scanned rows may be misread (item numbers: {issue})")

    if not items and not reasons:
        reasons.append("classified as a request but no line items could be extracted")
    result = Result(classification=kind, line_items=items)
    if reasons:
        result.needs_review = True
        result.review_reason = "; ".join(dict.fromkeys(reasons))[:1000]
    if kind == "rfq_revision":
        result.revises = parent
    return result
