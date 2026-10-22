"""Fail-closed bridge from risk checks to a PAPER-only broker."""
from decimal import Decimal as D
from risk_engine import Portfolio, Proposal, check_order
from paper_broker import PaperBroker, Quote

class TradingGate:
    def __init__(self, broker=None):
        self.broker = broker if broker is not None else PaperBroker()
        self.day_start_equity = D('2000')
        self.reserved_stops = {}

    def buy(self, order_id, quote: Quote, quantity, stop, now, fee=D('0')):
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity <= 0:
            return ['INVALID_QUANTITY']
        if order_id in self.broker.ids:
            return ['DUPLICATE_ORDER']
        if not self.broker._quote_ok(quote, now):
            return ['STALE_QUOTE']
        if quote.bid <= 0 or quote.ask < quote.bid or fee < 0:
            return ['INVALID_QUOTE']
        try:
            equity = self.broker.equity({s: (quote.bid if s == quote.symbol else D('0')) for s in self.broker.positions})
        except (ArithmeticError, ValueError):
            return ['INVALID_MARK']
        if any(qty > 0 and s != quote.symbol for s, qty in self.broker.positions.items()):
            return ['MISSING_PORTFOLIO_MARKS']
        exposure = sum(qty * quote.bid for s, qty in self.broker.positions.items())
        p = Portfolio(self.broker.cash, equity, self.day_start_equity, exposure)
        age = int((now - quote.observed_at).total_seconds())
        reasons = check_order(p, Proposal(quote.symbol, quantity, quote.ask, D(str(stop)), age))
        if quote.ask * quantity + fee > self.broker.cash - D('200'):
            reasons.append('FEE_RESERVE')
        if reasons:
            return reasons
        status = self.broker.buy(order_id, quote, quantity, now, fee)
        if status == 'FILLED_PAPER':
            self.reserved_stops[order_id] = D(str(stop))
        return [status]
