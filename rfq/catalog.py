"""data/catalog.csv: rows, the attribute vocabularies the model normalizes into, size parsing,
and the text-evidence rules code uses to check the model's attributes."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache

from rfq.config import ROOT

CATALOG_PATH = ROOT / "data" / "catalog.csv"
ATTRS = ("spec", "material", "ends", "extra")


@dataclass(frozen=True)
class Part:
    sku: str
    description: str
    product: str
    size: str
    spec: str
    material: str
    ends: str
    extra: str


@lru_cache(maxsize=1)
def parts() -> tuple[Part, ...]:
    if not CATALOG_PATH.exists():
        return ()
    with CATALOG_PATH.open(encoding="utf-8") as f:
        return tuple(
            Part(r["sku"], r["description"], r["product"].strip().lower(), r["size"].strip(),
                 r["spec"].strip(), r["material"].strip(), r["ends"].strip(), r["extra"].strip())
            for r in csv.DictReader(f)
        )


def extras_of(p: Part) -> set[str]:
    return {x.strip().lower() for x in p.extra.split(",") if x.strip()}


@lru_cache(maxsize=1)
def vocab() -> dict[str, tuple[str, ...]]:
    """Distinct non-empty values per attribute (extra split on commas), sorted."""
    ps = parts()
    v = {
        "product": sorted({p.product for p in ps}),
        "spec": sorted({p.spec for p in ps if p.spec}),
        "material": sorted({p.material for p in ps if p.material}),
        "ends": sorted({p.ends for p in ps if p.ends}),
        "extra": sorted({e for p in ps for e in extras_of(p)}),
    }
    return {k: tuple(vals) for k, vals in v.items()}


# ---------------------------------------------------------------- sizes
_NUM = re.compile(r"^(\d+)?(?:[\s-]*(\d+)/(\d+))?$|^(\d+(?:\.\d+)?)$")


def _part_value(s: str) -> Fraction | str | None:
    s = s.strip().lower().replace("″", "").replace('"', "").replace("''", "")
    s = re.sub(r"\s*(in|inch|inches)$", "", s).strip()
    s = re.sub(r"^(\d+/\d+)-\d+$", r"\1", s)  # bolt thread pitch: 3/4-10 -> 3/4
    s = re.sub(r"^(\d+)-(\d+)$", r"\1", s)  # 1-8 (1" UNC) -> 1 ; real mixed numbers have a slash
    if not s:
        return None
    if s in ("close", "cls"):
        return "close"
    m = _NUM.match(s)
    if not m:
        return s
    if m.group(4):
        return Fraction(m.group(4))
    whole = Fraction(int(m.group(1))) if m.group(1) else Fraction(0)
    if m.group(2):
        whole += Fraction(int(m.group(2)), int(m.group(3)))
    return whole


def parse_size(s: str | None) -> tuple | None:
    """'1-1/2' -> (3/2,); '8 x 6' -> (8, 6); '3/4 x close' -> (3/4, 'close'); '2.5' -> (5/2,)."""
    if not s or not s.strip():
        return None
    parts_ = [p for p in re.split(r"\s*[x×]\s*", s.strip(), flags=re.I) if p.strip()]
    # a length in feet ("3/4 x 6 ft" threaded rod) is not part of the nominal size
    parts_ = [p for p in parts_ if not re.fullmatch(r"\s*\d+(?:\.\d+)?\s*(?:ft|feet|foot|')\s*", p, re.I)]
    if not parts_:
        return None
    vals = tuple(_part_value(p) for p in parts_)
    return None if any(v is None for v in vals) else vals


# ---------------------------------------------------------------- text evidence
_TEXT_ALIASES = [  # applied to the customer's text before looking for evidence
    (r"\bseamless\b", "smls"), (r"\bgalvani[sz]ed\b", "galv"), (r"\bmalleable( iron)?\b", "mi"),
    (r"\bstainless( steel)?\b", "ss"), (r"\b(threaded|thrd|npt|fnpt|mnpt|screwed)\b", "thd"),
    (r"\bbutt[\s-]*weld(ed|ing)?\b", "bw"), (r"\bsocket[\s-]*weld(ed|ing)?\b", "sw"),
    (r"\braised[\s-]*face\b", "rf"), (r"\bflat[\s-]*face\b", "ff"), (r"\bring[\s-]*(type[\s-]*)?joint\b", "rtj"),
    (r"\bplain[\s-]*ends?\b", "pe"), (r"\bbevel(l?ed)?[\s-]*ends?\b", "be"),
    (r"\bthd both ends\b", "tbe"), (r"\bthd one end\b", "toe"),
    (r"\b(thd and coupled|thd and cpld|t/c|t & c)\b", "t&c"),
    (r"\bschedule\b", "sch"), (r"\bclass\s*(\d+)\b", r"\1#"), (r"\b(\d+)\s*(lb|lbs)\b", r"\1#"),
    (r"\blong[\s-]*radius\b", "lr"), (r"\bfull[\s-]*port\b", "full port"), (r"\bfp\b", "full port"),
    (r"\bstandard[\s-]*port\b", "std port"), (r"\bcarbon steel\b", "cs"),
]
_ENDS_EVIDENCE = {
    "THD": ["thd"], "BW": ["bw"], "SW": ["sw"], "RF": ["rf"], "FF": ["ff"], "RTJ": ["rtj"],
    "PE": ["pe"], "BE": ["be"], "TBE": ["tbe"], "TOE": ["toe"], "T&C": ["t&c"],
}


def norm_text(s: str) -> str:
    s = " " + s.lower().replace("″", '"') + " "
    for pat, rep in _TEXT_ALIASES:
        s = re.sub(pat, rep, s)
    return " ".join(s.split())


def _cores(value: str) -> list[str]:
    """Distinctive tokens of a catalog value: grade numbers (316l, 105, 40) and words >= 3 letters."""
    v = value.lower()
    out = re.findall(r"\d+[a-z]?", v) + [w for w in re.findall(r"[a-z]{3,}", v)
                                          if w not in ("sch", "smls", "erw", "galv")]
    special = re.findall(r"\b(smls|galv|mi|ss|cs|wcb|wpb)\b", v)
    return out + special


def has_evidence(attr: str, value: str, text: str) -> bool:
    """Does the customer's text support this catalog attribute value?"""
    t = norm_text(text)
    toks = set(re.findall(r"\d+[a-z]?|[a-z]+|t&c", t)) | set(re.findall(r"\d+#", t))
    if attr == "ends":
        return any(re.search(rf"(?<![a-z]){re.escape(e)}(?![a-z])", t) for e in _ENDS_EVIDENCE.get(value, [value.lower()]))
    if attr == "spec":
        num = re.search(r"\d+", value)
        return bool(num) and num.group(0) in re.findall(r"\d+", t)
    if attr == "extra":
        return value.lower() in t
    cores = _cores(value)
    return any(c in toks or c in t for c in cores) if cores else False
