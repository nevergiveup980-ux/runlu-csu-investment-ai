import type { BotPortfolioState, OpenOrder } from "./csu-bot-v2";

export type BrokerPosition = {
  symbol: string;
  quantity: number;
  averageCost?: number;
  marketValue?: number;
};

export type BrokerTransaction = {
  id?: string;
  symbol?: string;
  side?: string;
  quantity?: number;
  price?: number;
  date?: string;
  type?: string;
};

export type BrokerAccountSnapshot = {
  provider: string;
  accountId?: string;
  currency?: string;
  cash?: number;
  buyingPower?: number;
  positions: BrokerPosition[];
  openOrders?: OpenOrder[];
  transactions?: BrokerTransaction[];
  fetchedAt: string;
};

export interface ReadOnlyBrokerBridge {
  health(): Promise<{ connected: boolean; provider: string; mode: "READ_ONLY" }>;
  snapshot(): Promise<BrokerAccountSnapshot>;
}

export const BROKER_SAFETY = Object.freeze({
  mode: "READ_ONLY" as const,
  orderPlacement: false,
  orderModification: false,
  orderCancellation: false,
  liveExecution: false,
});

const normalizedSymbol = (symbol: string) => String(symbol || "").toUpperCase().replace(/\s/g, "");
const isCsu = (symbol: string) => ["CSU", "CSU.TO", "CSU:TSX"].includes(normalizedSymbol(symbol));

export function toBotPortfolio(snapshot: BrokerAccountSnapshot): BotPortfolioState {
  const csu = snapshot.positions.find((p) => isCsu(p.symbol));
  return {
    shares: Math.max(0, Math.trunc(csu?.quantity || 0)),
    cash: snapshot.cash ?? null,
    buyingPower: snapshot.buyingPower ?? null,
    averageCost: csu?.averageCost ?? null,
    currency: snapshot.currency ?? "CAD",
    openOrders: (snapshot.openOrders || []).filter((o) => isCsu(o.symbol)),
    historyCount: snapshot.transactions?.length ?? null,
  };
}

export function accountDiagnostics(snapshot: BrokerAccountSnapshot) {
  const cash = snapshot.cash ?? null;
  const buyingPower = snapshot.buyingPower ?? null;
  const buyingPowerGap = cash != null && buyingPower != null ? Math.max(0, cash - buyingPower) : null;
  const openCsuOrders = (snapshot.openOrders || []).filter((o) => isCsu(o.symbol));
  const limitBuyReserve = openCsuOrders
    .filter((o) => o.side === "BUY")
    .reduce((sum, o) => sum + Math.max(0, Number(o.quantity) || 0) * Math.max(0, Number(o.limitPrice) || 0), 0);

  return {
    provider: snapshot.provider,
    mode: BROKER_SAFETY.mode,
    currency: snapshot.currency ?? "CAD",
    cash,
    buyingPower,
    buyingPowerGap,
    openCsuOrders,
    transactionCount: snapshot.transactions?.length ?? 0,
    reserveReconciliation: buyingPowerGap == null
      ? "UNKNOWN"
      : Math.abs(limitBuyReserve - buyingPowerGap) <= 1
        ? "MATCHES_OPEN_LIMIT_BUYS"
        : "REVIEW_DIFFERENCE",
    liveExecution: false,
  };
}

export function assertBrokerWriteDisabled(action: string): never {
  throw new Error(`Broker write blocked by CSU Bot V2 safety boundary: ${action}`);
}
