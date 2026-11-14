#!/usr/bin/env python3
"""btc-cent-forecast-01 entry: conservative mean reversion off persistence.

Reads /input/<id>.in (one case), writes /output/<id>.out.
Forecast: last price adjusted by small mean reversion on the 1-hour return
before the checkpoint. Keeps close to persistence (hard to beat) with a
tiny downward/upward nudge when recent momentum is strong.
"""

import json
import math
import os
import sys
from pathlib import Path

MIN_PRICE = 0.00001
MAX_PRICE = 9_999_999.99999

# Mean reversion coefficient on the 1-hour return before the checkpoint.
# Negative = fade recent momentum. Small: -0.05 means if price rose 1% in
# the last hour, predict 0.05% lower. Large enough to help slightly, small
# enough that it can't hurt much if the signal is noise.
COEF = -0.05


def price5(x: float) -> float:
    return round(min(MAX_PRICE, max(MIN_PRICE, x)) * 1e5) / 1e5


def forecast(prices: list[float]) -> float:
    if not prices:
        raise ValueError("no prices")
    x = prices[-1]
    if not math.isfinite(x) or x <= 0:
        raise ValueError("bad last price")
    # 1-hour return before checkpoint (60 minutes back, if available)
    if len(prices) >= 61:
        r1h = math.log(x / prices[-61])
    else:
        r1h = 0.0
    pred = x * math.exp(-COEF * r1h)
    return price5(pred)


def main() -> None:
    input_dir = Path(os.environ.get("MAKEFUN_INPUT_DIR", "/input"))
    output_dir = Path(os.environ.get("MAKEFUN_OUTPUT_DIR", "/output"))
    output_dir.mkdir(parents=True, exist_ok=True)

    inputs = sorted(f for f in input_dir.iterdir() if f.suffix == ".in")
    for infile in inputs:
        case_id = infile.stem
        with open(infile, "r", encoding="utf-8") as fh:
            case = json.load(fh)
        markets = case.get("markets", [])
        if len(markets) != 1:
            raise ValueError(f"{case_id}: expected 1 market, got {len(markets)}")
        prices = markets[0].get("prices", [])
        guess = forecast(prices)
        out = {"forecasts": [{"case": case_id, "price": guess}]}
        with open(output_dir / f"{case_id}.out", "w", encoding="utf-8") as fh:
            fh.write(json.dumps(out) + "\n")


if __name__ == "__main__":
    main()
