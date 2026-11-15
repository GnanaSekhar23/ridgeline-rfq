"""Command line: `rfq parse --emails <dir> --out parsed.json` (or `python -m rfq parse ...`)."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from rfq.config import MODEL


def _write_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def cmd_parse(args: argparse.Namespace) -> int:
    import os

    from rfq.pipeline import run_inbox

    emails_dir = Path(args.emails)
    if not emails_dir.is_dir():
        print(f"--emails: not a directory: {emails_dir}", file=sys.stderr)
        return 1
    if args.offline:
        os.environ["RFQ_OFFLINE"] = "1"
    results, runlog = run_inbox(emails_dir, model=args.model)
    _write_json_atomic(Path(args.out), results)
    rows = runlog.rows
    calls = sum(r.get("live_calls", 0) for r in rows)
    hits = sum(1 for r in rows if r.get("cache_hit"))
    errs = sum(1 for r in rows if r.get("error"))
    paid = sum(r.get("live_cost_usd", 0) for r in rows)
    print(f"wrote {len(results)} emails to {args.out} | model calls: {calls}, cache hits: {hits}, "
          f"no answer: {errs}, paid this run: ${paid:.4f} | log: {runlog.dir}")
    return 0


def cmd_estimate(args: argparse.Namespace) -> int:
    """Price a run before making it: render every prompt, count tokens approximately."""
    from rfq.estimate import estimate_email
    from rfq.extractors import extract_all
    from rfq.mime import parse_message
    from rfq.pipeline import link_inbox
    from rfq.prompt import build_messages

    emails = [parse_message(p.read_bytes(), p.stem) for p in sorted(Path(args.emails).glob("*.eml"))]
    dups, _ = link_inbox(emails)
    print(f"model {args.model}; {len(dups)} duplicate(s) skipped\n")
    print(f"{'email':8} {'in tok':>8} {'out tok':>8} {'imgs':>4} {'$':>8}")
    tot_in = tot_out = 0
    tot = 0.0
    for e in emails:
        if e.id in dups:
            continue
        docs = extract_all(e)
        est = estimate_email(e.id, args.model, build_messages(e, docs)[0], docs)
        tot_in += est.input_tokens
        tot_out += est.output_tokens
        tot += est.cost_usd
        print(f"{e.id:8} {est.input_tokens:>8,} {est.output_tokens:>8,} {est.images:>4} {est.cost_usd:>8.4f}")
    print(f"{'TOTAL':8} {tot_in:>8,} {tot_out:>8,} {'':>4} {tot:>8.4f}")
    return 0


def cmd_inspect(args: argparse.Namespace) -> int:
    """Dump how the MIME layer sees each email (no model calls)."""
    from rfq.extractors import describe_docs, extract_all
    from rfq.mime import describe, parse_message

    target = Path(args.path)
    paths = sorted(target.glob("*.eml")) if target.is_dir() else [target]
    chunks = []
    for p in paths:
        try:
            email = parse_message(p.read_bytes(), p.stem)
            chunks.append(describe(email) + describe_docs(extract_all(email)))
        except Exception as e:
            chunks.append(f"===== {p.stem}\nPARSE ERROR: {type(e).__name__}: {e}\n")
    text = "\n".join(chunks)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"wrote {len(paths)} emails to {args.out}")
    else:
        print(text)
    return 0


def cmd_links(args: argparse.Namespace) -> int:
    """Show duplicate and thread links found in code (no model calls)."""
    from rfq.mime import parse_message
    from rfq.pipeline import link_inbox

    emails = []
    for p in sorted(Path(args.emails).glob("*.eml")):
        try:
            emails.append(parse_message(p.read_bytes(), p.stem))
        except Exception as e:
            print(f"{p.stem}: PARSE ERROR {type(e).__name__}: {e}")
    dups, parents = link_inbox(emails)
    for e in emails:
        bits = []
        if e.id in dups:
            bits.append(f"duplicate_of={dups[e.id]}")
        if e.id in parents:
            bits.append(f"thread_parent={parents[e.id]}")
        if bits:
            print(f"{e.id}: {'  '.join(bits)}   [{e.headers.get('subject')}]")
    print(f"{len(dups)} duplicate(s), {len(parents)} thread link(s)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="rfq", description="Ridgeline RFQ inbox parser")
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("parse", help="parse every .eml in a directory")
    p.add_argument("--emails", required=True, help="directory of .eml files")
    p.add_argument("--out", required=True, help="output JSON path")
    p.add_argument("--model", default=MODEL, help=f"OpenAI model (default {MODEL})")
    p.add_argument("--offline", action="store_true", help="never call the model; cache only")
    p.set_defaults(func=cmd_parse)
    es = sub.add_parser("estimate", help="estimate tokens and cost of a run (no model calls)")
    es.add_argument("--emails", required=True, help="directory of .eml files")
    es.add_argument("--model", default=MODEL)
    es.set_defaults(func=cmd_estimate)
    i = sub.add_parser("inspect", help="show how emails are split (no model calls)")
    i.add_argument("path", help=".eml file or directory")
    i.add_argument("--out", help="write to this file instead of stdout")
    i.set_defaults(func=cmd_inspect)
    lk = sub.add_parser("links", help="show duplicate / thread links (no model calls)")
    lk.add_argument("--emails", required=True, help="directory of .eml files")
    lk.set_defaults(func=cmd_links)
    return ap


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
