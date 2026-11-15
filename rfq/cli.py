"""Command line: `rfq parse --emails <dir> --out parsed.json` (or `python -m rfq parse ...`)."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from rfq.pipeline import process_inbox


def _write_json_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def cmd_parse(args: argparse.Namespace) -> int:
    emails_dir = Path(args.emails)
    if not emails_dir.is_dir():
        print(f"--emails: not a directory: {emails_dir}", file=sys.stderr)
        return 1
    results = process_inbox(emails_dir)
    _write_json_atomic(Path(args.out), results)
    print(f"wrote {len(results)} emails to {args.out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="rfq", description="Ridgeline RFQ inbox parser")
    sub = ap.add_subparsers(dest="command", required=True)
    p = sub.add_parser("parse", help="parse every .eml in a directory")
    p.add_argument("--emails", required=True, help="directory of .eml files")
    p.add_argument("--out", required=True, help="output JSON path")
    p.set_defaults(func=cmd_parse)
    return ap


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
