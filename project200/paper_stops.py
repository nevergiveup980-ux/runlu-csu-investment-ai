"""On-demand PAPER stop simulation only; never submits live orders.

Tracks remaining buy lots using FIFO against historical sells, so previously
closed lots cannot trigger a stop on a later new position. Stop fills use the
observed bid, not the intended stop, to represent gap risk.
"""
from collections import deque
from decimal import Decimal as D, InvalidOperation
from paper_broker import Quote
from trading_gate import valid_quote

def _active_stops(gate):
    lots = {}
    for event in gate.broker.events:
        symbol = event["symbol"]
        qty = event["qty"]
        if type(qty) is not int or qty <= 0:
            raise ValueError("INVALID_JOURNAL")
        queue = lots.setdefault(symbol, deque())
        if event["side"] == "BUY":
            stop = gate.reserved_stops.get(event["id"])
            if stop is None:
                raise ValueError("MISSING_STOP")
            try:
                stop = D(str(stop))
                if not stop.is_finite() or stop <= 0:
                    raise ValueError("INVALID_STOP")
            except (InvalidOperation, TypeError) as exc:
                raise ValueError("INVALID_STOP") from exc
            queue.append([qty, stop])
        elif event["side"] == "SELL":
            left = qty
            while left and queue:
                lot = queue[0]
                used = min(left, lot[0])
                lot[0] -= used
                left -= used
                if lot[0] == 0:
                    queue.popleft()
            if left:
                raise ValueError("INVALID_JOURNAL")
        else:
            raise ValueError("INVALID_JOURNAL")
    return {symbol: (sum(lot[0] for lot in queue), max((lot[1] for lot in queue), default=None))
            for symbol, queue in lots.items()}

def evaluate_stops(gate, quotes, now, *, fee=D("0")):
    broker = gate.broker
    try:
        fee = D(str(fee))
        if not fee.is_finite() or fee < 0:
            return {"status": "INVALID_FEE", "fills": []}
    except (TypeError, ValueError, InvalidOperation):
        return {"status": "INVALID_FEE", "fills": []}
    open_positions = {s: q for s, q in broker.positions.items() if q > 0}
    if not open_positions:
        return {"status": "NO_POSITIONS", "fills": []}
    for symbol in open_positions:
        quote = quotes.get(symbol)
        if not isinstance(quote, Quote) or quote.symbol != symbol or not valid_quote(quote):
            return {"status": "INVALID_OR_MISSING_QUOTE", "fills": []}
        if not broker._quote_ok(quote, now):
            return {"status": "STALE_QUOTE", "fills": []}
    try:
        stops = _active_stops(gate)
    except ValueError as exc:
        return {"status": str(exc), "fills": []}
    if any(stops.get(s, (None, None))[0] != q or stops[s][1] is None for s, q in open_positions.items()):
        return {"status": "POSITION_JOURNAL_MISMATCH", "fills": []}
    fills = []
    for symbol, quantity in open_positions.items():
        quote = quotes[symbol]
        stop = stops[symbol][1]
        if D(str(quote.bid)) > stop:
            continue
        order_id = "PAPER_STOP:" + symbol + ":" + now.isoformat()
        result = broker.sell(order_id, quote, quantity, now, fee)
        if result != "FILLED_PAPER":
            return {"status": result, "fills": fills}
        fills.append({"symbol": symbol, "quantity": quantity, "stop": str(stop),
                      "fill_bid": str(quote.bid), "order_id": order_id})
    return {"status": "STOP_FILLED_PAPER" if fills else "NO_STOP_TRIGGER", "fills": fills}
