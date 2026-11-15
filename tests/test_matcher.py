"""Matcher: code decides from normalized attributes against data/catalog.csv.
Parts are picked from the catalog dynamically — no SKUs hard-coded."""

from __future__ import annotations

from collections import Counter

from rfq.catalog import parse_size, parts, vocab
from rfq.matcher import match_line
from rfq.schema import Attrs


def A(**kw) -> Attrs:
    base = {"product": None, "size": None, "spec": None, "material": None, "ends": None, "extra": None}
    return Attrs(**{**base, **kw})


def _unique_part():
    """A catalog part whose product+size+spec+material+ends is unique."""
    key = lambda p: (p.product, parse_size(p.size), p.spec, p.material, p.ends, p.extra)
    counts = Counter(key(p) for p in parts())
    return next(p for p in parts() if counts[key(p)] == 1 and p.spec and p.material and p.ends and p.size)


def _text(p) -> str:
    return f'{p.size}" {p.product} {p.spec} {p.material} {p.ends} {p.extra}'


def test_exact_attributes_match_one_part() -> None:
    p = _unique_part()
    m = match_line(A(product=p.product, size=p.size, spec=p.spec, material=p.material, ends=p.ends,
                     extra=p.extra.split(",")[0].strip().lower() or None), _text(p))
    assert (m.match, m.sku) == ("matched", p.sku) and p.description in m.reason


def test_one_attribute_off_is_not_in_catalog_with_nearest() -> None:
    p = _unique_part()
    same = [q for q in parts() if q.product == p.product and parse_size(q.size) == parse_size(p.size)]
    other_spec = next(s for s in vocab()["spec"] if s not in {q.spec for q in same})
    m = match_line(A(product=p.product, size=p.size, spec=other_spec, material=p.material, ends=p.ends),
                   f"{_text(p)} {other_spec}")
    assert m.match == "not_in_catalog" and m.sku is None
    assert "nearest" in m.reason and "spec" in m.reason


def test_product_and_size_only_is_ambiguous_with_candidates() -> None:
    by = Counter((p.product, parse_size(p.size)) for p in parts())
    (product, size_key), n = next((k, n) for k, n in by.most_common() if n > 2 and k[1])
    size = next(p.size for p in parts() if p.product == product and parse_size(p.size) == size_key)
    m = match_line(A(product=product, size=size), f'{size}" {product}')
    assert m.match == "ambiguous" and m.sku is None and len(m.candidates) == min(n, 10)
    assert "differ by" in m.reason


def test_other_values_and_unknown_product_are_not_in_catalog() -> None:
    p = _unique_part()
    assert match_line(A(product="other", size="2"), "2in widget").match == "not_in_catalog"
    m = match_line(A(product=p.product, size=p.size, material="other"), _text(p) + " inconel")
    assert m.match == "not_in_catalog" and "material" in m.reason


def test_size_not_stocked_is_not_in_catalog() -> None:
    p = _unique_part()
    m = match_line(A(product=p.product, size="37", spec=p.spec), f'37" {p.product} {p.spec}')
    assert m.match == "not_in_catalog" and 'in 37"' in m.reason


def test_unsupported_attribute_is_ignored_not_trusted() -> None:
    p = _unique_part()
    # model claims a material the text never mentions -> ignored, so it cannot force a match
    m = match_line(A(product=p.product, size=p.size, material=p.material), f'{p.size}" {p.product}')
    assert "ignored unsupported material" in m.reason
    assert m.match in ("ambiguous", "matched")
    if m.match == "matched":  # only if the product+size alone is unique in the catalog
        assert sum(1 for q in parts() if q.product == p.product and parse_size(q.size) == parse_size(p.size)) == 1


def test_missing_size_or_product_is_ambiguous() -> None:
    assert match_line(A(product="tee"), "tee").match == "ambiguous"
    assert match_line(None, "x").match == "ambiguous"


def test_parse_size_equivalences() -> None:
    assert parse_size("1-1/2") == parse_size('1 1/2"') == parse_size("1.5")
    assert parse_size("6 x 4") == parse_size('6" x 4"')
    assert parse_size("3/4 x close") == parse_size("3/4 X CLOSE")


def test_bolt_thread_pitch_is_not_part_of_the_size() -> None:
    """A stud written with its thread pitch ('D"-11 x L') is the catalog's 'D x L'."""
    studs = sorted({p.size for p in parts() if p.product == "stud bolt" and " x " in p.size})
    size = studs[-1]  # any stocked stud works; taken from the catalog, not hard-coded
    dia, length = size.split(" x ")
    assert parse_size(f'{dia}"-11 x {length}') == parse_size(size)
    assert parse_size(f"{dia}-11 x {length}") == parse_size(size)


def _P(sku, product="pipe", size="2", spec="SCH 80", material="", ends="PE", extra=""):
    from rfq.catalog import Part

    return Part(sku, sku, product, size, spec, material, ends, extra)


def test_less_specific_material_agrees_but_different_does_not() -> None:
    from rfq.matcher import _agrees

    assert _agrees("material", "GALV", _P("a", material="MI GALV"))
    assert _agrees("material", "GALV", _P("b", material="A53 GALV"))
    assert not _agrees("material", "MI GALV", _P("c", material="GALV"))  # catalog less specific: no
    assert not _agrees("material", "316 SS", _P("d", material="304 SS"))
    assert not _agrees("material", "A105", _P("e", material="A182 F316L"))


def test_threaded_satisfied_by_threaded_both_ends_only() -> None:
    from rfq.matcher import _agrees

    assert _agrees("ends", "THD", _P("a", ends="TBE")) and _agrees("ends", "THD", _P("b", ends="THD"))
    assert not _agrees("ends", "THD", _P("c", ends="TOE")) and not _agrees("ends", "TBE", _P("d", ends="THD"))


def test_null_attribute_narrows_only_by_text_evidence() -> None:
    from rfq.matcher import _narrow_by_text

    cands = [_P("316l", size="3", spec="SCH 10", material="A312 TP316L"),
             _P("304l", size="3", spec="SCH 10", material="A312 TP304L")]
    kept, notes = _narrow_by_text(cands, {"spec": "SCH 10"}, "PROCESS LINES - SCH 10 TP316L: 3in pipe, beveled end")
    assert [p.sku for p in kept] == ["316l"] and "material" in notes[0]
    kept, notes = _narrow_by_text(cands, {"spec": "SCH 10"}, "3in pipe, beveled end")  # no evidence
    assert len(kept) == 2 and not notes
    kept, _ = _narrow_by_text(cands, {"material": "A312 TP304L"}, "316l")  # stated attrs are not re-narrowed
    assert len(kept) == 2


def test_length_in_feet_is_not_part_of_the_size() -> None:
    assert parse_size("3/4-10 x 6 ft") == parse_size("3/4") == parse_size("3/4 x 6'")
    assert parse_size("6 ft") is None


def test_output_fields_only_when_matcher_ran() -> None:
    import sys
    from pathlib import Path

    from rfq.models import LineItem, Result

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "data"))
    from check_format import check

    plain = Result("rfq", line_items=[LineItem("r", "d", 1, "EA", "body")]).to_json()
    assert "match" not in plain["line_items"][0]
    matched = Result("rfq", line_items=[LineItem("r", "d", 1, "EA", "body", sku="RL-1", match="matched",
                                                 match_reason="x")]).to_json()
    amb = Result("rfq", line_items=[LineItem("r", "d", 1, "EA", "body", match="ambiguous",
                                             match_reason="y", candidates=["RL-1", "RL-2"])]).to_json()
    assert "candidates" not in matched["line_items"][0]
    assert check({"E1": matched, "E2": amb, "E3": plain}) == []
