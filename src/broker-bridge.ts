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


export function validateSnapshot(snapshot: BrokerAccountSnapshot, maxAgeMinutes = 15) {
  const errors: string[] = [];
  const warnings: string[] = [];

  if (!snapshot || typeof snapshot !== "object") {
    return { valid: false, errors: ["Broker snapshot is missing"], warnings, ageMinutes: null };
  }
  if (!snapshot.provider) errors.push("Broker provider is missing");
  if (!Array.isArray(snapshot.positions)) errors.push("Positions must be an array");
  if (!Array.isArray(snapshot.openOrders)) errors.push("Open orders must be an array");
  if (snapshot.cash == null || snapshot.buyingPower == null) errors.push("Cash and buying power are required");
  if (snapshot.currency !== "CAD") errors.push("CAD cash account required");
  if (Array.isArray(snapshot.positions) && snapshot.positions.some(p => !p || !Number.isInteger(p.quantity) || p.quantity < 0)) errors.push("Position quantity invalid");
  if (snapshot.cash != null && (!Number.isFinite(snapshot.cash) || snapshot.cash < 0)) errors.push("Cash is invalid");
  if (snapshot.buyingPower != null && (!Number.isFinite(snapshot.buyingPower) || snapshot.buyingPower < 0)) errors.push("Buying power is invalid");

  const fetched = Date.parse(snapshot.fetchedAt || "");
  const ageMinutes = Number.isFinite(fetched) ? (Date.now() - fetched) / 60000 : Infinity;
  if (!Number.isFinite(fetched)) errors.push("Snapshot timestamp is invalid");
  else if (ageMinutes < -5) errors.push("Snapshot timestamp is unexpectedly in the future");
  else if (ageMinutes > maxAgeMinutes) errors.push(`Broker snapshot is stale (${Math.round(ageMinutes)} minutes old)`);

  const csuOrders = Array.isArray(snapshot.openOrders) ? snapshot.openOrders : [];
  for (const order of csuOrders) {
    if (!order.symbol || !Number.isFinite(order.quantity) || order.quantity <= 0) errors.push("Open order contains invalid symbol or quantity");
    if (order.side === "BUY" && order.limitPrice != null && (!Number.isFinite(order.limitPrice) || order.limitPrice <= 0)) errors.push("Open BUY limit price is invalid");
  }

  if (snapshot.cash != null && snapshot.buyingPower != null && snapshot.buyingPower > snapshot.cash) {
    warnings.push("Buying power exceeds cash; verify whether broker margin or unsettled-funds semantics are involved");
  }

  return { valid: errors.length === 0, errors, warnings, ageMinutes: Number.isFinite(ageMinutes) ? ageMinutes : null };
}
