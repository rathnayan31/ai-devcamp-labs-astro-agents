"""Price an eval run from its usage log (one JSON line per model call).

    uv run python evals/cost.py evals/.runs/<run>.usage.jsonl [--cases 6]

run.sh writes the log (PIXEL_ASTRO_USAGE_LOG) and calls this. Thinking tokens
are billed as output. Judge and user-simulator calls aren't in the log: they
go through the eval framework, not the agent.

PRICES are USD per 1M tokens, Vertex AI standard tier, as of 2026-10-25.
gemini-3.8-flash is Google's introductory rate (through 2026-12-31; list
price $1.50 / $7.50). The Flash-Lite figures come from third-party snapshots.
Check https://cloud.google.com/vertex-ai/generative-ai/pricing before quoting
the dollars; the token counts are exact.
"""

from __future__ import annotations

import argparse
import collections
import json

PRICES = {  # model: (input, cached input, output incl. thinking)
    "gemini-3.8-flash": (0.75, 0.075, 3.75),
    "gemini-3.5-flash-lite": (0.30, 0.03, 2.50),
    "gemini-3.1-flash-lite": (0.25, 0.025, 1.50),
}


def cost(model: str, prompt: int, cached: int, output: int, thinking: int) -> float:
    price_in, price_cached, price_out = PRICES.get(model, (float("nan"),) * 3)
    return ((prompt - cached) * price_in + cached * price_cached + (output + thinking) * price_out) / 1e6


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("log")
    parser.add_argument("--cases", type=int, default=0, help="cases in the run, for a per-case figure")
    args = parser.parse_args()

    by_model: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for line in open(args.log):
        call = json.loads(line)
        totals = by_model[call["model"]]
        totals["calls"] += 1
        for key in ("prompt", "cached", "output", "thinking"):
            totals[key] += call[key]

    total = 0.0
    print(f"{'model':24s} {'calls':>5s} {'input':>8s} {'cached':>7s} {'output':>7s} {'thinking':>8s} {'USD':>9s}")
    for model, t in sorted(by_model.items()):
        usd = cost(model, t["prompt"], t["cached"], t["output"], t["thinking"])
        total += usd
        print(f"{model:24s} {t['calls']:5d} {t['prompt']:8d} {t['cached']:7d} {t['output']:7d} {t['thinking']:8d} {usd:9.5f}")
    calls = sum(t["calls"] for t in by_model.values())
    thinking = sum(t["thinking"] for t in by_model.values())
    billed_out = sum(t["output"] + t["thinking"] for t in by_model.values())
    print(f"TOTAL: {calls} model calls, ${total:.5f}"
          + (f", ${total / args.cases:.5f} per case" if args.cases else "")
          + (f"; thinking is {100 * thinking / billed_out:.0f}% of billed output" if billed_out else ""))


if __name__ == "__main__":
    main()
