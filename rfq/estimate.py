"""Offline cost estimate: render every prompt, count tokens approximately, price them.

Text: ~3.5 characters per token (tables of numbers tokenize worse than prose).
Images: OpenAI's published sizing rules — tile-based (gpt-4o / gpt-4.1 family) or
patch-based (gpt-4.1-mini). Output: ~70 tokens per likely item line + fixed overhead.
These are estimates; the real run logs actual usage.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from rfq.config import PRICES
from rfq.models import Doc

CHARS_PER_TOKEN = 3.5
OUT_TOKENS_PER_ITEM = 70
OUT_OVERHEAD = 120
ITEMS_PER_IMAGE_GUESS = 15


def image_tokens(model: str, w: int, h: int, detail: str = "high") -> int:
    if model.startswith("gpt-4.1-mini") or model.startswith("gpt-4.1-nano"):
        mult = 1.62 if "mini" in model else 2.46
        patches = math.ceil(w / 32) * math.ceil(h / 32)
        if patches > 1536:
            r = math.sqrt(32 * 32 * 1536 / (w * h))
            patches = min(1536, math.ceil(w * r / 32) * math.ceil(h * r / 32))
        return math.ceil(patches * mult)
    base, per_tile = (2833, 5667) if model.startswith("gpt-4o-mini") else (85, 170)
    if detail == "low":
        return base
    s = min(1.0, 2048 / max(w, h))
    w, h = w * s, h * s
    s = min(1.0, 768 / min(w, h))
    w, h = w * s, h * s
    return base + per_tile * math.ceil(w / 512) * math.ceil(h / 512)


@dataclass
class Estimate:
    email: str
    input_tokens: int
    output_tokens: int
    images: int
    cost_usd: float


def estimate_email(email_id: str, model: str, messages: list[dict], docs: list[Doc]) -> Estimate:
    chars = 0
    for m in messages:
        c = m["content"]
        parts = [{"type": "text", "text": c}] if isinstance(c, str) else c
        chars += sum(len(p["text"]) for p in parts if p["type"] == "text")
    imgs = [im for d in docs for im in d.images]
    in_tok = int(chars / CHARS_PER_TOKEN) + sum(image_tokens(model, im.width, im.height) for im in imgs)
    item_like = sum(
        1 for d in docs for ln in d.lines
        if re.search(r"\d", ln.text) and not ln.struck and not ln.row_id.startswith("body!Q")
    )
    out_tok = OUT_OVERHEAD + OUT_TOKENS_PER_ITEM * (item_like + ITEMS_PER_IMAGE_GUESS * len(imgs))
    p_in, _, p_out = PRICES.get(model, (0.0, 0.0, 0.0))
    return Estimate(email_id, in_tok, out_tok, len(imgs), (in_tok * p_in + out_tok * p_out) / 1e6)
