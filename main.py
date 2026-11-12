import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bars

SYMBOL = "CBBTC"
EMA_N = 120
WARMUP = EMA_N + 1
ENTRY_EDGE = 0.002        # price must clear the EMA by 0.2%
TAKE_PCT = 0.006          # take 0.6%
STOP_PCT = 0.015          # stop 1.5%
MAX_HOLD = 240            # bars
COOLDOWN = 10             # bars after an exit
MAX_SLIPPAGE_BPS = 80
MIN_TRADE = 1_000_000     # 1 USDC

_ema = None
_seen = 0
_held = 0
_last_exit_seq = -999


def on_batch(state, batch):
    global _ema, _seen, _held, _last_exit_seq

    bar = None
    for b in batch["bars"]:
        if b["symbol"] == SYMBOL:
            bar = b
            break
    if bar is None:
        return []

    c = int(bar["c"])
    _seen += 1
    if _ema is None:
        _ema = float(c)
    else:
        k = 2.0 / (EMA_N + 1)
        _ema = c * k + _ema * (1.0 - k)

    held = state.positions.get(SYMBOL)
    if held is not None and int(held.qty) > 0:
        _held += 1
        qty = int(held.qty)
        cost = int(held.cost)
        hi_val = state.value(SYMBOL, qty, int(bar["h"]))
        lo_val = state.value(SYMBOL, qty, int(bar["l"]))
        if hi_val * 1000 >= cost * 1006 or lo_val * 100 <= cost * 985 or _held >= MAX_HOLD:
            _held = 0
            _last_exit_seq = state.seq
            return [{
                "side": "sell",
                "symbol": SYMBOL,
                "qty": str(qty),
                "max_slippage_bps": MAX_SLIPPAGE_BPS,
            }]
        return []

    if state.warming_up or _seen < WARMUP:
        return []
    if state.seq - _last_exit_seq < COOLDOWN:
        return []
    if c <= _ema * (1.0 + ENTRY_EDGE):
        return []

    spend = state.cash
    room = state.hello["caps"]["max_weight_bps"] * state.equity // 10000
    if spend > room:
        spend = room
    if spend < MIN_TRADE:
        return []

    _held = 0
    return [{
        "side": "buy",
        "symbol": SYMBOL,
        "notional_quote_units": str(spend),
        "max_slippage_bps": MAX_SLIPPAGE_BPS,
    }]


makefun_bars.run(on_batch)
