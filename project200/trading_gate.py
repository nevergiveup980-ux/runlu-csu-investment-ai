"""Paper-only order gateway. Requires fresh marks for every open position."""
from decimal import Decimal as D, InvalidOperation
from risk_engine import Portfolio, Proposal, check_order
from paper_broker import PaperBroker, Quote

class TradingGate:
    def __init__(self, broker=None):
        self.broker = broker if broker is not None else PaperBroker()
        self.day_start_equity = D("2000")
        self.reserved_stops = {}

    def buy(self, order_id, quote: Quote, quantity, stop, now, fee=D("0"), marks=None):
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
            return ["INVALID_QUANTITY"]
        if order_id in self.broker.ids:
            return ["DUPLICATE_ORDER"]
        if not self.broker._quote_ok(quote, now):
            return ["STALE_QUOTE"]
        if quote.bid <= 0 or quote.ask < quote.bid:
            return ["INVALID_QUOTE"]
        try:
            fee = D(str(fee))
            stop = D(str(stop))
            if not fee.is_finite() or fee < 0 or not stop.is_finite():
                return ["INVALID_COST_OR_STOP"]
        except (InvalidOperation, ValueError, TypeError):
            return ["INVALID_COST_OR_STOP"]
        marks = dict(marks or {})
        marks[quote.symbol] = quote
        bid_marks = {}
        for symbol, qty in self.broker.positions.items():
            if qty <= 0:
                continue
            mark = marks.get(symbol)
            if not isinstance(mark, Quote) or mark.symbol != symbol:
                return ["MISSING_PORTFOLIO_MARKS"]
            if not self.broker._quote_ok(mark, now) or mark.bid <= 0 or mark.ask < mark.bid:
                return ["INVALID_PORTFOLIO_MARKS"]
            bid_marks[symbol] = mark.bid
        equity = self.broker.equity(bid_marks)
        exposure = sum(D(qty) * bid_marks[s] for s, qty in self.broker.positions.items() if qty > 0)
        p = Portfolio(self.broker.cash, equity, self.day_start_equity, exposure)
        age = (now - quote.observed_at).total_seconds()
        reasons = check_order(p, Proposal(quote.symbol, quantity, quote.ask, stop, int(age)))
        if quote.ask * quantity + fee > self.broker.cash - D("200"):
            reasons.append("FEE_RESERVE")
        if reasons:
            return list(dict.fromkeys(reasons))
        result = self.broker.buy(order_id, quote, quantity, now, fee)
        if result == "FILLED_PAPER":
            self.reserved_stops[order_id] = stop
        return [result]
