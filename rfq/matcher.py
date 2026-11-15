"""Catalog matching — code decides; the model only normalized the line into catalog terms.

  1. product + numeric size must agree (no size, or no catalog product -> not a match).
  2. spec / material / ends / extra: when the customer stated one (and the text supports the
     model's normalization), it must agree — a part one attribute off is a wrong quote. Agreement
     is exact, except a less specific material ("GALV" ⊆ "MI GALV") and threaded = TBE.
     "other" = stated but not a value we stock -> nothing can match.
  2b. Still several parts: an attribute the model left null may narrow them by a catalog value the
     customer's text supports (e.g. a heading or sheet name stating the material), only if a
     part survives.
  3. 0 parts -> not_in_catalog; 1 -> matched; >1 -> ambiguous (the customer must choose).
An attribute the model filled in without support in the customer's text is ignored (logged in
the reason): that can only widen the candidate set (ambiguous), never force a wrong part.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from rfq.catalog import ATTRS, Part, extras_of, has_evidence, parse_size, parts

MAX_CANDIDATES = 10


@dataclass
class Match:
    match: str  # matched | not_in_catalog | ambiguous
    sku: str | None
    reason: str
    candidates: list[str] = field(default_factory=list)


# Customer end type -> catalog end types that satisfy it ("threaded" nipple = threaded both ends).
_ENDS_OK = {"THD": {"THD", "TBE"}}


def _tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", s.lower()))


def _agrees(attr: str, value: str, p: Part) -> bool:
    if attr == "extra":
        return value.lower() in extras_of(p)
    have = getattr(p, attr)
    if attr == "ends":
        return have.upper() in _ENDS_OK.get(value.upper(), {value.upper()})
    if attr == "material":
        # the customer's material may be less specific than the catalog's:
        # "GALV" is satisfied by "MI GALV" (fittings) or "A53 GALV" (pipe) — every stated token present
        want = _tokens(value)
        return bool(want) and want <= _tokens(have)
    return have.lower() == value.lower()


def _narrow_by_text(cands: list[Part], given: dict[str, str], text: str) -> tuple[list[Part], list[str]]:
    """Several parts left: for an attribute the model left null, keep the parts whose value the
    customer's own text supports (e.g. a sheet name or heading that states the material).
    Only narrows when at least one part survives; never adds an attribute the text lacks."""
    notes = []
    for a in ATTRS:
        if a in given or len(cands) < 2:
            continue
        if a == "extra":
            values = {e for p in cands for e in extras_of(p)}
            ok = {v for v in values if has_evidence(a, v, text)}
            keep = [p for p in cands if extras_of(p) & ok]
        else:
            values = {getattr(p, a) for p in cands if getattr(p, a)}
            ok = {v for v in values if has_evidence(a, v, text)}
            keep = [p for p in cands if getattr(p, a) in ok]
        if ok and keep and len(keep) < len(cands):
            cands = keep
            notes.append(f"{a} {'/'.join(sorted(ok))} from text")
    return cands, notes


def _spec_text(product: str, size: str | None, used: dict[str, str]) -> str:
    bits = [f'{size}"' if size else "", product] + [used[a] for a in ATTRS if a in used]
    return " ".join(b for b in bits if b)


def _differs(cands: list[Part]) -> str:
    """Which attributes distinguish the candidates (for an ambiguous reason)."""
    diff = [a for a in ATTRS if len({getattr(p, a) for p in cands}) > 1]
    return ", ".join(diff) or "description"


def _nearest(base: list[Part], used: dict[str, str]) -> str:
    """For not_in_catalog: the stocked part that misses by the fewest stated attributes."""
    if not base:
        return ""
    def misses(p: Part) -> list[str]:
        return [f"{a} {getattr(p, a) or '-'}" for a, v in used.items() if v != "other" and not _agrees(a, v, p)]
    best = min(base, key=lambda p: len(misses(p)))
    m = misses(best)
    return f"; nearest {best.sku} {best.description} differs: {', '.join(m)}" if m else ""


def match_line(attrs, text: str) -> Match:
    """attrs: schema.Attrs (or None); text: the line's description + raw (evidence for attrs)."""
    catalog = parts()
    if not catalog:
        return Match("ambiguous", None, "catalog not available")
    if attrs is None or not attrs.product:
        return Match("ambiguous", None, "product not identified")
    product = attrs.product
    if product == "other":
        return Match("not_in_catalog", None, "product type not in the catalog")
    size_key = parse_size(attrs.size)
    if size_key is None:
        n = sum(1 for p in catalog if p.product == product)
        return Match("ambiguous", None, f"{product}: size not stated ({n} stocked sizes)")

    base = [p for p in catalog if p.product == product and parse_size(p.size) == size_key]
    used: dict[str, str] = {}
    ignored: list[str] = []
    for a in ATTRS:
        v = getattr(attrs, a)
        if not v:
            continue
        if v == "other" or has_evidence(a, v, text):
            used[a] = v
        else:
            ignored.append(f"{a} {v}")
    note = f" (ignored unsupported {', '.join(ignored)})" if ignored else ""
    want = _spec_text(product, attrs.size, used)

    if not base:
        return Match("not_in_catalog", None, f'{want}: no stocked {product} in {attrs.size}"{note}')
    if any(v == "other" for v in used.values()):
        odd = ", ".join(a for a, v in used.items() if v == "other")
        return Match("not_in_catalog", None, f"{want}: stated {odd} not stocked for this item{note}")
    cands = [p for p in base if all(_agrees(a, v, p) for a, v in used.items())]
    if not cands:
        return Match("not_in_catalog", None, f"{want}: no stocked part with all stated attributes"
                     f"{_nearest(base, used)}{note}")
    cands, narrowed = _narrow_by_text(cands, used, text)
    if narrowed:
        note += f" ({'; '.join(narrowed)})"
    if len(cands) == 1:
        p = cands[0]
        return Match("matched", p.sku, f"{want}: one part fits — {p.description}{note}")
    return Match("ambiguous", None, f"{want}: {len(cands)} parts fit, differ by {_differs(cands)}{note}",
                 candidates=[p.sku for p in cands[:MAX_CANDIDATES]])
