"""cbBTC/USDC trend-following bot for the make.fun bars-replay race.

Long only, one position at a time. Enters when the close clears a 40-bar EMA
by 0.4%, exits on a +0.6% take, a -2% stop, or a 240-bar time stop, with a
20-bar cooldown after each exit. Low turnover on purpose: on a choppy or
falling tape it sits in cash instead of bleeding fees.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bars

SYMBOL = "CBBTC"
EMA_N = 40
WARMUP = EMA_N + 1
ENTRY_EDGE = 0.004        # close must clear the EMA by 0.4%
TAKE_PCT = 0.006          # take 0.6%
STOP_PCT = 0.02           # stop 2%
MAX_HOLD = 240            # bars
COOLDOWN = 20             # bars after an exit
MAX_SLIPPAGE_BPS = 80
MIN_TRADE = 1_000_000     # 1 USDC

TAKE_NUM = int((1.0 + TAKE_PCT) * 1000)
STOP_NUM = int((1.0 - STOP_PCT) * 1000)

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
        if hi_val * 1000 >= cost * TAKE_NUM or lo_val * 1000 <= cost * STOP_NUM or _held >= MAX_HOLD:
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
