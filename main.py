import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor"))

import makefun_bars

SYMBOL = "CBBTC"
LOOKBACK = 45
ENTRY_Z = -1.30          # buy only on a real wash-out
EXIT_Z = -0.10           # back to ~mean: close
STOP_PCT = 0.012         # hard stop 1.2%
TAKE_PCT = 0.009         # take 0.9%
COOLDOWN_BARS = 3
SPEND_FRACTION = 4       # spend cash // 4 per entry
MAX_SLIPPAGE_BPS = 80
MIN_TRADE = 1_000_000    # 1 USDC in micro-USDC

_closes = []
_last_trade_seq = -999


def on_batch(state, batch):
    global _closes, _last_trade_seq

    bar = None
    for b in batch["bars"]:
        if b["symbol"] == SYMBOL:
            bar = b
            break
    if bar is None:
        return []

    c = int(bar["c"])
    _closes.append(c)
    if len(_closes) > LOOKBACK:
        del _closes[0]

    held = state.positions.get(SYMBOL)
    has_pos = held is not None and int(held.qty) > 0

    # Exit first, always allowed (even during warmup the replay rejects, harmless).
    if has_pos:
        qty = int(held.qty)
        cost = int(held.cost)
        entry = cost / qty if qty > 0 else c
        pnl = (c - entry) / entry if entry > 0 else 0.0
        mean = sum(_closes) / len(_closes)
        z = ((c - mean) / _std()) if len(_closes) >= 20 else 0.0

        if pnl <= -STOP_PCT or pnl >= TAKE_PCT or (len(_closes) >= 20 and z >= EXIT_Z):
            _last_trade_seq = state.seq
            return [{"side": "sell", "symbol": SYMBOL, "qty": str(qty), "max_slippage_bps": MAX_SLIPPAGE_BPS}]
        return []

    if state.warming_up:
        return []
    if len(_closes) < 20:
        return []
    if state.seq - _last_trade_seq < COOLDOWN_BARS:
        return []

    mean = sum(_closes) / len(_closes)
    std = _std()
    z = (c - mean) / std if std > 0 else 0.0
    if z > ENTRY_Z:
        return []

    spend = state.cash // SPEND_FRACTION
    room = state.hello["caps"]["max_weight_bps"] * state.equity // 10000
    if spend > room:
        spend = room
    if spend < MIN_TRADE:
        return []

    _last_trade_seq = state.seq
    return [{"side": "buy", "symbol": SYMBOL, "notional_quote_units": str(spend), "max_slippage_bps": MAX_SLIPPAGE_BPS}]


def _std():
    n = len(_closes)
    if n < 2:
        return 0.0
    mean = sum(_closes) / n
    var = sum((x - mean) ** 2 for x in _closes) / n
    return var ** 0.5


makefun_bars.run(on_batch)
