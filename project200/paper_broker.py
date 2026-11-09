"""Deterministic PAPER broker. No live brokerage imports or execution."""
from dataclasses import dataclass
from decimal import Decimal as D, InvalidOperation
from datetime import datetime

@dataclass(frozen=True)
class Quote:
    symbol: str
    bid: D
    ask: D
    observed_at: datetime

def _valid_numbers(quote, fee):
    try:
        bid, ask, cost = D(str(quote.bid)), D(str(quote.ask)), D(str(fee))
        return all(x.is_finite() for x in (bid, ask, cost)) and bid > 0 and ask >= bid and cost >= 0
    except (ValueError, TypeError, InvalidOperation, AttributeError):
        return False

class PaperBroker:
    def __init__(self, cash=D("2000")):
        cash=D(str(cash))
        if not cash.is_finite() or cash < D("200"):
            raise ValueError("INVALID_INITIAL_CASH")
        self.cash = cash
        self.positions = {}
        self.events = []
        self.ids = set()

    def _quote_ok(self, quote, now):
        if not isinstance(quote, Quote) or not isinstance(quote.observed_at, datetime) or not isinstance(now, datetime):
            return False
        if quote.observed_at.tzinfo is None or now.tzinfo is None:
            return False
        age = (now - quote.observed_at).total_seconds()
        return 0 <= age <= 60

    def _valid_order(self, order_id, quote, quantity, fee):
        return (isinstance(order_id, str) and bool(order_id.strip())
                and isinstance(quote.symbol, str) and bool(quote.symbol.strip())
                and type(quantity) is int and quantity > 0 and _valid_numbers(quote, fee))

    def buy(self, order_id, quote, quantity, now, fee=D("0")):
        if order_id in self.ids:
            return "DUPLICATE_ORDER"
        if not self._quote_ok(quote, now):
            return "STALE_QUOTE"
        if not self._valid_order(order_id, quote, quantity, fee):
            return "INVALID_ORDER"
        cost = D(str(quote.ask)) * quantity + D(str(fee))
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
        if not self._valid_order(order_id, quote, quantity, fee):
            return "INVALID_ORDER"
        if self.positions.get(quote.symbol, 0) < quantity:
            return "INSUFFICIENT_POSITION"
        proceeds = D(str(quote.bid)) * quantity - D(str(fee))
        if self.cash + proceeds < 0:
            return "INSUFFICIENT_CASH_FOR_FEE"
        self.cash += proceeds
        self.positions[quote.symbol] -= quantity
        self.ids.add(order_id)
        self.events.append({"id":order_id,"side":"SELL","symbol":quote.symbol,"qty":quantity,"fill":str(quote.bid),"fee":str(fee),"time":now.isoformat()})
        return "FILLED_PAPER"

    def equity(self, bids):
        total = self.cash
        for symbol, qty in self.positions.items():
            if qty <= 0:
                continue
            try:
                bid = D(str(bids[symbol]))
                if not bid.is_finite() or bid <= 0:
                    raise ValueError("INVALID_MARK")
            except (KeyError, TypeError, InvalidOperation) as exc:
                raise ValueError("INVALID_MARK") from exc
            total += bid * qty
        return total
