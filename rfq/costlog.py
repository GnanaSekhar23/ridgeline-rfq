"""Per-run logs and the cost report.

runs/<run_id>/calls.jsonl     one line per email: cache hit?, tokens, $, latency, error
runs/<run_id>/failures.jsonl  emails that could not get a model answer, with `retryable`
runs/latest/                  copy of the most recent run (committed)
reports/cost.md               totals and per-email table
Never contains the API key or request content.
"""

from __future__ import annotations

import json
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path

from rfq.config import REPORTS_DIR, RUNS_DIR


class RunLog:
    def __init__(self, model: str, runs_dir: Path = RUNS_DIR, reports_dir: Path = REPORTS_DIR) -> None:
        self.model = model
        # timestamp for humans + random suffix so two runs in the same second never share a folder
        self.run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)
        self.dir = runs_dir / self.run_id
        self.dir.mkdir(parents=True, exist_ok=False)
        self.runs_dir = runs_dir
        self.reports_dir = reports_dir
        self.rows: list[dict] = []

    def _append(self, name: str, row: dict) -> None:
        with (self.dir / name).open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    def record(self, email_id: str, outcome=None, *, skipped: str | None = None, n_images: int = 0) -> None:
        if outcome is None:
            row = {"email": email_id, "skipped": skipped, "live_calls": 0, "cache_hit": False,
                   "input_tokens": 0, "cached_input_tokens": 0, "output_tokens": 0,
                   "cost_usd": 0.0, "live_cost_usd": 0.0, "latency_s": 0.0, "images": 0, "error": None}
        else:
            row = {
                "email": email_id, "skipped": None, "model": self.model,
                "cache_hit": outcome.cache_hit, "live_calls": outcome.live_calls,
                "input_tokens": outcome.usage.input_tokens,
                "cached_input_tokens": outcome.usage.cached_input_tokens,
                "output_tokens": outcome.usage.output_tokens,
                "cost_usd": outcome.cost_usd, "live_cost_usd": outcome.live_cost_usd,
                "latency_s": outcome.latency_s, "images": n_images,
                "prompt_truncated": outcome.prompt_truncated, "error": outcome.error,
            }
            if outcome.error:
                self._append("failures.jsonl", {"email": email_id, "error": outcome.error,
                                                "retryable": outcome.retryable})
        self.rows.append(row)
        self._append("calls.jsonl", row)

    def finish(self) -> Path:
        report = self.render()
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        (self.reports_dir / "cost.md").write_text(report, encoding="utf-8")
        (self.dir / "cost.md").write_text(report, encoding="utf-8")
        latest = self.runs_dir / "latest"
        if latest.exists():
            shutil.rmtree(latest)
        shutil.copytree(self.dir, latest)
        return self.reports_dir / "cost.md"

    def render(self) -> str:
        rows = self.rows
        modelled = [r for r in rows if not r.get("skipped")]
        tot = {k: sum(r.get(k, 0) or 0 for r in rows) for k in
               ("live_calls", "input_tokens", "cached_input_tokens", "output_tokens", "cost_usd", "live_cost_usd")}
        hits = sum(1 for r in rows if r.get("cache_hit"))
        errors = sum(1 for r in rows if r.get("error"))
        n = max(len(modelled), 1)
        out = [
            "# Cost report", "",
            f"Run `{self.run_id}`, model `{self.model}`. Prices: `rfq/config.py` PRICES (USD per 1M tokens).", "",
            "| | value |", "|---|---|",
            f"| emails | {len(rows)} ({len(rows) - len(modelled)} skipped: duplicates) |",
            f"| model calls sent this run | {tot['live_calls']} |",
            f"| answers from cache | {hits} |",
            f"| emails with no model answer | {errors} |",
            f"| input tokens (of which cached by provider) | {tot['input_tokens']:,} ({tot['cached_input_tokens']:,}) |",
            f"| output tokens | {tot['output_tokens']:,} |",
            f"| **cost to produce these answers** | **${tot['cost_usd']:.4f}** |",
            f"| cost paid by this run | ${tot['live_cost_usd']:.4f} |",
            f"| per modelled email: calls / tokens / $ | {sum(1 for r in modelled if r.get('cache_hit') or r.get('live_calls'))/n:.2f} / "
            f"{(tot['input_tokens'] + tot['output_tokens'])/n:,.0f} / ${tot['cost_usd']/n:.4f} |",
            "", "Cost to produce = what the original call cost, also for answers now replayed from cache.", "",
            "| email | from cache | calls | in | cached in | out | $ | latency s | images | note |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for r in rows:
            note = r.get("skipped") or (r.get("error") or "")[:80]
            out.append(
                f"| {r['email']} | {'yes' if r.get('cache_hit') else ''} | {r.get('live_calls', 0)} | "
                f"{r.get('input_tokens', 0):,} | {r.get('cached_input_tokens', 0):,} | {r.get('output_tokens', 0):,} | "
                f"{r.get('cost_usd', 0):.4f} | {r.get('latency_s', 0)} | {r.get('images', 0)} | {note} |"
            )
        return "\n".join(out) + "\n"
