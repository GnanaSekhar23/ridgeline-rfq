#!/usr/bin/env python3
"""Score parsed.json against the dev answer key, following data/README.md "What we grade".

    python eval/eval.py parsed.json
    python eval/eval.py parsed.json --detail lines          # per-line failures only
    python eval/eval.py parsed.json --emails E003,E007      # restrict to some emails
    python eval/eval.py parsed.json --baseline reports/eval.json   # what changed since last run

Writes reports/eval.md (human) and reports/eval.json (per-email/per-line outcomes, for diffs).
This is the ONLY code in the repo allowed to read answer_key.json.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from rapidfuzz import fuzz

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_KEY = ROOT / "data" / "dev" / "answer_key.json"
REQUEST_KINDS = {"rfq", "rfq_revision", "purchase_order"}
PAIR_THRESHOLD = 60.0  # rapidfuzz token_sort_ratio on normalised raw text
DETAILS = ("all", "summary", "classes", "lines", "links", "review")

# ---------------------------------------------------------------- phrase normalisation
# Both the description and the key phrase go through the same rewrite, then all
# non-alphanumerics are dropped and we test substring containment.
_ABBREV = [  # catalog abbreviations -> long form
    (r"\bells?\b", "elbow"),
    (r"\bvlvs?\b", "valve"),
    (r"\bflgs?\b", "flange"),
    (r"\bgskts?\b", "gasket"),
    (r"\bspw\b", "spiral wound"),
    (r"\bmi\b", "malleable iron"),
    (r"\bcs\b", "carbon steel"),
    (r"\bfp\b", "full port"),
    (r"\bcplgs?\b", "coupling"),
    (r"\bred(ucer|ucing)?\b", "reduc"),
]
_SHORT = [  # spelled-out spec -> short form
    (r"\bschedule\b", "sch"),
    (r"\bclass\s*(\d+)\b", r"\1lb"),
    (r"\b(\d+)\s*(?:#|lbs?\b|pound\b)", r"\1lb"),
    (r"\bbutt[\s-]*weld(?:ed|ing)?\b", "bw"),
    (r"\b(?:threaded|thrd|thd|npt)\b", "thd"),
    (r"\bseamless\b", "smls"),
    (r"\bgalvani[sz]ed\b|\bgalv\b", "galv"),
]


def phrase_tokens(s: str) -> list[str]:
    s = s.lower()
    for pat, rep in _ABBREV + _SHORT:
        s = re.sub(pat, rep, s)
    return re.findall(r"[a-z0-9]+", s)


def _contains(desc_toks: list[str], phrase_toks: list[str]) -> bool:
    """True if a run of whole description tokens, concatenated, equals the phrase.

    Spaces/punctuation are ignored ("sch 40" == "Sch-40" == "sch40"), but a match must start
    and end on token boundaries, so "sch40" does not match inside "sch400" and "reduc" does not
    match inside "reduced". A plural "s"/"es" on the last token is allowed ("elbows").
    """
    target = "".join(phrase_toks)
    if not target:
        return False
    accept = {target, target + "s", target + "es"}
    for i in range(len(desc_toks)):
        acc = ""
        for tok in desc_toks[i:]:
            acc += tok
            if acc in accept:
                return True
            if len(acc) >= len(target) + 2:
                break
    return False


def mentions(desc: str, phrase: str) -> bool:
    """`phrase` may be "a|b" = either."""
    d = phrase_tokens(desc)
    return any(_contains(d, phrase_tokens(alt)) for alt in phrase.split("|") if alt.strip())


def norm_raw(s: str) -> str:
    return " ".join(re.findall(r"\d+/\d+|\d+(?:\.\d+)?|[a-z]+", (s or "").lower()))


# ---------------------------------------------------------------- pairing
def pair_lines(key: list[dict], pred: list[dict]) -> list[tuple[int, int, float]]:
    """Greedy best-first one-to-one pairing on raw-text similarity."""
    kn = [norm_raw(k.get("raw", "")) for k in key]
    pn = [norm_raw(p.get("raw", "")) for p in pred]
    scores = []
    for i, a in enumerate(kn):
        for j, b in enumerate(pn):
            sc = fuzz.token_sort_ratio(a, b)
            if sc >= PAIR_THRESHOLD:
                scores.append((sc, i, j))
    scores.sort(reverse=True)
    used_k, used_p, pairs = set(), set(), []
    for sc, i, j in scores:
        if i in used_k or j in used_p:
            continue
        used_k.add(i)
        used_p.add(j)
        pairs.append((i, j, sc))
    return pairs


def qty_ok(k: dict, p: dict) -> bool | None:
    tol = k.get("qty_tol")
    if tol is None:
        return None  # unscored
    kq, pq = k.get("qty"), p.get("qty")
    if kq is None or pq is None:
        return kq is None and pq is None
    if tol == 0:
        return float(kq) == float(pq)
    return abs(float(pq) - float(kq)) <= tol * abs(float(kq))


def uom_ok(k: dict, p: dict) -> bool:
    return (k.get("uom") or "EA") == (p.get("uom") or "EA")


def source_ok(k: dict, p: dict) -> bool:
    return (k.get("source") or "").strip().lower() == (p.get("source") or "").strip().lower()


def context(k: dict, p: dict) -> tuple[bool, list[str], list[str]]:
    desc = p.get("description") or ""
    missing = [m for m in k.get("must_mention", []) if not mentions(desc, m)]
    present = [m for m in k.get("must_not_mention", []) if mentions(desc, m)]
    return (not missing and not present), missing, present


# ---------------------------------------------------------------- scoring
@dataclass
class Score:
    n_emails: int = 0
    class_correct: int = 0
    silent_losses: list[str] = field(default_factory=list)
    lost: list[str] = field(default_factory=list)
    phantom: list[str] = field(default_factory=list)
    confusions: list[str] = field(default_factory=list)
    key_lines: int = 0
    pred_lines: int = 0
    paired: int = 0
    hallucinated: list[str] = field(default_factory=list)
    missed: list[str] = field(default_factory=list)
    qty_scored: int = 0
    qty_right: int = 0
    uom_right: int = 0
    source_right: int = 0
    ctx_right: int = 0
    line_fails: list[str] = field(default_factory=list)
    link_total: int = 0
    link_right: int = 0
    link_fails: list[str] = field(default_factory=list)
    rev_tp: int = 0
    rev_fp: int = 0
    rev_fn: int = 0
    review_fails: list[str] = field(default_factory=list)
    per_email: dict = field(default_factory=dict)


def _pct(a: int, b: int) -> str:
    return f"{100 * a / b:.1f}% ({a}/{b})" if b else "n/a"


def score(key: dict, pred: dict, only: set[str] | None = None) -> Score:
    s = Score()
    for eid in sorted(key):
        if only and eid not in only:
            continue
        k = key[eid]
        p = pred.get(eid) or {"classification": None, "line_items": [], "needs_review": False}
        s.n_emails += 1
        rec: dict = {"lines": {}}
        kc, pc = k["classification"], p.get("classification")
        rec["class"] = [kc, pc]
        if kc == pc:
            s.class_correct += 1
        else:
            s.confusions.append(f"{eid}: key={kc} pred={pc}")
        if kc in REQUEST_KINDS and pc not in REQUEST_KINDS:
            s.lost.append(eid)
        if kc not in REQUEST_KINDS and pc in REQUEST_KINDS:
            s.phantom.append(eid)

        klines, plines = k.get("line_items", []), p.get("line_items") or []
        needs_action = bool(klines) or bool(k.get("needs_review"))
        if needs_action and not plines and not p.get("needs_review"):
            s.silent_losses.append(eid)

        s.key_lines += len(klines)
        s.pred_lines += len(plines)
        pairs = pair_lines(klines, plines)
        s.paired += len(pairs)
        pk = {i for i, _, _ in pairs}
        pp = {j for _, j, _ in pairs}
        for i, kl in enumerate(klines):
            if i not in pk:
                s.missed.append(f"{kl['id']}: {kl['raw']!r}")
                rec["lines"][kl["id"]] = "missed"
        for j, pl in enumerate(plines):
            if j not in pp:
                s.hallucinated.append(f"{eid}: {pl.get('raw')!r} [{pl.get('source')}]")
        rec["hallucinated"] = len(plines) - len(pp)

        for i, j, _ in pairs:
            kl, pl = klines[i], plines[j]
            q = qty_ok(kl, pl)
            u, src = uom_ok(kl, pl), source_ok(kl, pl)
            c, missing, present = context(kl, pl)
            if q is not None:
                s.qty_scored += 1
                s.qty_right += q
            s.uom_right += u
            s.source_right += src
            s.ctx_right += c
            probs = []
            if q is False:
                probs.append(f"qty {pl.get('qty')} != {kl.get('qty')}")
            if not u:
                probs.append(f"uom {pl.get('uom')} != {kl.get('uom')}")
            if not src:
                probs.append(f"source {pl.get('source')!r} != {kl.get('source')!r}")
            if missing:
                probs.append(f"missing {missing}")
            if present:
                probs.append(f"must-not {present}")
            rec["lines"][kl["id"]] = "ok" if not probs else "; ".join(probs)
            if probs:
                s.line_fails.append(
                    f"{kl['id']}: {'; '.join(probs)}\n    desc: {pl.get('description')!r}"
                )

        for f in ("revises", "duplicate_of"):
            kv, pv = k.get(f), p.get(f)
            if kv is None and pv is None:
                continue
            s.link_total += 1
            if kv == pv:
                s.link_right += 1
            else:
                s.link_fails.append(f"{eid}.{f}: key={kv} pred={pv}")

        kr, pr = bool(k.get("needs_review")), bool(p.get("needs_review"))
        s.rev_tp += kr and pr
        s.rev_fp += pr and not kr
        s.rev_fn += kr and not pr
        if kr != pr:
            s.review_fails.append(f"{eid}: key={kr} pred={pr} reason={p.get('review_reason')!r}")
        rec["needs_review"] = [kr, pr]
        s.per_email[eid] = rec
    return s


def headline(s: Score) -> dict:
    return {
        "silent_losses": len(s.silent_losses),
        "hallucinated_lines": len(s.hallucinated),
        "lost_requests": len(s.lost),
        "phantom_requests": len(s.phantom),
        "classification": _pct(s.class_correct, s.n_emails),
        "line_recall": _pct(s.paired, s.key_lines),
        "line_precision": _pct(s.paired, s.pred_lines),
        "qty": _pct(s.qty_right, s.qty_scored),
        "uom": _pct(s.uom_right, s.paired),
        "source": _pct(s.source_right, s.paired),
        "context_carried": _pct(s.ctx_right, s.paired),
        "links": _pct(s.link_right, s.link_total),
        "review_precision": _pct(s.rev_tp, s.rev_tp + s.rev_fp),
        "review_recall": _pct(s.rev_tp, s.rev_tp + s.rev_fn),
    }


def render(s: Score, detail: str) -> str:
    out = ["# Eval vs dev answer key", "", "| metric | value |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in headline(s).items()]

    def section(name: str, title: str, items: list[str]) -> None:
        if detail in ("all", name) and items:
            out.extend(["", f"## {title} ({len(items)})", "", "```"])
            out.extend(items)
            out.append("```")

    section("classes", "Silent losses", s.silent_losses)
    section("classes", "Classification errors", s.confusions)
    section("lines", "Missed key lines", s.missed)
    section("lines", "Hallucinated / unpaired predicted lines", s.hallucinated)
    section("lines", "Paired-line field errors", s.line_fails)
    section("links", "Link errors", s.link_fails)
    section("review", "needs_review errors", s.review_fails)
    return "\n".join(out) + "\n"


def diff(old: dict, new: dict) -> list[str]:
    changes = []
    for eid in sorted(set(old) | set(new)):
        o, n = old.get(eid, {}), new.get(eid, {})
        for f in ("class", "needs_review", "hallucinated"):
            if o.get(f) != n.get(f):
                changes.append(f"{eid}.{f}: {o.get(f)} -> {n.get(f)}")
        ol, nl = o.get("lines", {}), n.get("lines", {})
        for lid in sorted(set(ol) | set(nl)):
            if ol.get(lid) != nl.get(lid):
                changes.append(f"{lid}: {ol.get(lid)} -> {nl.get(lid)}")
    return changes


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("parsed", type=Path)
    ap.add_argument("--key", type=Path, default=DEFAULT_KEY)
    ap.add_argument("--detail", choices=DETAILS, default="summary", help="what to print to stdout")
    ap.add_argument("--emails", help="comma-separated email ids to score")
    ap.add_argument("--baseline", type=Path, help="previous eval.json to diff against")
    ap.add_argument("--reports", type=Path, default=ROOT / "reports")
    a = ap.parse_args(argv)

    key = json.loads(a.key.read_text(encoding="utf-8"))["emails"]
    pred = json.loads(a.parsed.read_text(encoding="utf-8"))
    only = set(a.emails.split(",")) if a.emails else None
    s = score(key, pred, only)

    baseline = None
    if a.baseline and a.baseline.exists():
        baseline = json.loads(a.baseline.read_text(encoding="utf-8")).get("per_email", {})

    a.reports.mkdir(parents=True, exist_ok=True)
    if not only:  # only full runs overwrite the reports
        (a.reports / "eval.md").write_text(render(s, "all"), encoding="utf-8")
        (a.reports / "eval.json").write_text(
            json.dumps({"headline": headline(s), "per_email": s.per_email}, indent=1) + "\n",
            encoding="utf-8",
        )
    print(render(s, a.detail))
    if baseline is not None:
        changes = diff(baseline, s.per_email)
        print(f"## Changes vs baseline ({len(changes)})")
        print("\n".join(changes) or "(none)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
