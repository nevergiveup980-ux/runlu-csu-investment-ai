export type Holding = {
  id: string;
  symbol: string;
  exchange?: string;
  name?: string;
  currency?: string;
  shares?: number;
  averageCost?: number;
};

export type InvestmentMemory = {
  id: string;
  holdingId: string;
  occurredAt: string;
  action: "BUY" | "ADD" | "REDUCE" | "SELL" | "NOTE" | "REVIEW";
  quantity?: number;
  price?: number;
  reason?: string;
  note?: string;
};

export type Portfolio = {
  id: string;
  name: string;
  holdings: Holding[];
};

export const READ_ONLY = true as const;

export function assertReadOnly(action: string): never {
  throw new Error(`RUNLU INVEST is read-only. Blocked action: ${action}`);
}
