"""Explicitly invoked stop simulation; no background monitoring or live orders.

If multiple lots of a symbol exist, a breach of any lot stop liquidates the
entire paper position at the observed bid. This is deliberately conservative.
"""
from decimal import Decimal as D, InvalidOperation
from paper_broker import Quote

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
    from trading_gate import valid_quote
    for symbol in open_positions:
        quote = quotes.get(symbol)
        if not isinstance(quote, Quote) or quote.symbol != symbol or not valid_quote(quote):
            return {"status": "INVALID_OR_MISSING_QUOTE", "fills": []}
        if not broker._quote_ok(quote, now):
            return {"status": "STALE_QUOTE", "fills": []}
    stops = {}
    for event in broker.events:
        if event["side"] != "BUY" or broker.positions.get(event["symbol"], 0) <= 0:
            continue
        stop = gate.reserved_stops.get(event["id"])
        if stop is None:
            return {"status": "MISSING_STOP", "fills": []}
        try:
            stop = D(str(stop))
            if not stop.is_finite() or stop <= 0:
                return {"status": "INVALID_STOP", "fills": []}
        except (ValueError, TypeError, InvalidOperation):
            return {"status": "INVALID_STOP", "fills": []}
        stops[event["symbol"]] = max(stops.get(event["symbol"], D("0")), stop)
    if set(open_positions) != set(stops):
        return {"status": "MISSING_STOP", "fills": []}
    fills = []
    for symbol, quantity in open_positions.items():
        quote = quotes[symbol]
        if D(str(quote.bid)) > stops[symbol]:
            continue
        order_id = "PAPER_STOP:" + symbol + ":" + now.isoformat()
        result = broker.sell(order_id, quote, quantity, now, fee)
        if result != "FILLED_PAPER":
            return {"status": result, "fills": fills}
        fills.append({"symbol": symbol, "quantity": quantity, "stop": str(stops[symbol]),
                      "fill_bid": str(quote.bid), "order_id": order_id})
    return {"status": "STOP_FILLED_PAPER" if fills else "NO_STOP_TRIGGER", "fills": fills}
