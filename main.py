import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bars

SYMBOL = "CBBTC"
LOOKBACK = 20
ENTRY_Z = -0.30          # enter on any mild wash-out
TAKE_PCT = 0.004         # take 0.4% bounce
EMERGENCY_STOP = 0.10    # 10% backstop only
COOLDOWN_BARS = 5
MAX_SLIPPAGE_BPS = 80
MIN_TRADE = 1_000_000    # 1 USDC

_closes = []
_last_exit_seq = -999


def on_batch(state, batch):
    global _closes, _last_exit_seq

    bar = None
    for b in batch["bars"]:
        if b["symbol"] == SYMBOL:
            bar = b
            break
    if bar is None:
        return []

    closes_before = list(_closes)
    c = int(bar["c"])
    _closes.append(c)
    if len(_closes) > LOOKBACK:
        del _closes[0]

    held = state.positions.get(SYMBOL)
    if held is not None and int(held.qty) > 0:
        qty = int(held.qty)
        cost = int(held.cost)
        hi_val = state.value(SYMBOL, qty, int(bar["h"]))
        lo_val = state.value(SYMBOL, qty, int(bar["l"]))
        hit_take = hi_val * 1000 >= cost * 1004
        hit_stop = lo_val * 100 <= cost * 90
        if hit_take or hit_stop:
            _last_exit_seq = state.seq
            return [{
                "side": "sell",
                "symbol": SYMBOL,
                "qty": str(qty),
                "max_slippage_bps": MAX_SLIPPAGE_BPS,
            }]
        return []

    if state.warming_up or len(closes_before) < LOOKBACK:
        return []
    if state.seq - _last_exit_seq < COOLDOWN_BARS:
        return []

    mean = sum(closes_before) / len(closes_before)
    var = sum((x - mean) ** 2 for x in closes_before) / len(closes_before)
    std = var ** 0.5
    if std <= 0:
        return []
    z = (c - mean) / std
    if z > ENTRY_Z:
        return []

    spend = state.cash
    room = state.hello["caps"]["max_weight_bps"] * state.equity // 10000
    if spend > room:
        spend = room
    if spend < MIN_TRADE:
        return []

    return [{
        "side": "buy",
        "symbol": SYMBOL,
        "notional_quote_units": str(spend),
        "max_slippage_bps": MAX_SLIPPAGE_BPS,
    }]


makefun_bars.run(on_batch)
