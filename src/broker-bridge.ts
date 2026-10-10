export type BrokerAccountSnapshot = {
  provider: string;
  accountId?: string;
  currency?: string;
  cash?: number;
  buyingPower?: number;
  positions: Array<{
    symbol: string;
    quantity: number;
    averageCost?: number;
    marketValue?: number;
  }>;
  openOrders?: Array<Record<string, unknown>>;
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

export function assertBrokerWriteDisabled(action: string): never {
  throw new Error(`Broker write blocked by CSU Bot V2 safety boundary: ${action}`);
}
