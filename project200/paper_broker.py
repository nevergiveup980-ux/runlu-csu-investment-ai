"""Deterministic PAPER broker. No live brokerage imports or execution."""
from dataclasses import dataclass
from decimal import Decimal as D
from datetime import datetime

@dataclass(frozen=True)
class Quote:
    symbol: str
    bid: D
    ask: D
    observed_at: datetime

class PaperBroker:
    def __init__(self, cash=D("2000")):
        self.cash = cash
        self.positions = {}
        self.events = []
        self.ids = set()

    def _quote_ok(self, quote, now):
        if quote.observed_at.tzinfo is None or now.tzinfo is None:
            return False
        age = (now - quote.observed_at).total_seconds()
        return 0 <= age <= 60

    def buy(self, order_id, quote, quantity, now, fee=D("0")):
        if order_id in self.ids:
            return "DUPLICATE_ORDER"
        if not self._quote_ok(quote, now):
            return "STALE_QUOTE"
        if quantity <= 0 or quote.bid <= 0 or quote.ask < quote.bid or fee < 0:
            return "INVALID_ORDER"
        cost = quote.ask * quantity + fee
        if cost > self.cash - D("200"):
            return "CASH_RESERVE"
        self.cash -= cost
        self.positions[quote.symbol] = self.positions.get(quote.symbol, 0) + quantity
        self.ids.add(order_id)
        self.events.append({"id":order_id,"side":"BUY","symbol":quote.symbol,"qty":quantity,"fill":str(quote.ask),"fee":str(fee),"time":now.isoformat()})
        return "FILLED_PAPER"

    def sell(self, order_id, quote, quantity, now, fee=D("0")):
        if order_id in self.ids:
            return "DUPLICATE_ORDER"
        if not self._quote_ok(quote, now):
            return "STALE_QUOTE"
        if quantity <= 0 or quote.bid <= 0 or quote.ask < quote.bid or fee < 0:
            return "INVALID_ORDER"
        if self.positions.get(quote.symbol, 0) < quantity:
            return "INSUFFICIENT_POSITION"
        self.cash += quote.bid * quantity - fee
        self.positions[quote.symbol] -= quantity
        self.ids.add(order_id)
        self.events.append({"id":order_id,"side":"SELL","symbol":quote.symbol,"qty":quantity,"fill":str(quote.bid),"fee":str(fee),"time":now.isoformat()})
        return "FILLED_PAPER"

    def equity(self, bids):
        return self.cash + sum(D(str(bids[s])) * q for s,q in self.positions.items())
