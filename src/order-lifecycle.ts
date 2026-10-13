/** Pure order lifecycle model. No network calls or broker writes. */
export type OrderPhase =
  | "PROPOSED" | "APPROVED" | "REJECTED" | "EXPIRED"
  | "SUBMISSION_UNKNOWN" | "BROKER_ACCEPTED" | "PARTIALLY_FILLED"
  | "FILLED" | "CANCELLED" | "BROKER_REJECTED" | "HALTED";

export type OrderRecord = {
  proposalId: string;
  phase: OrderPhase;
  createdAt: string;
  expiresAt: string;
  approvedAt?: string;
  brokerOrderId?: string;
  filledQuantity: number;
  requestedQuantity: 1;
  reason?: string;
};

export type OrderEvent =
  | { type: "APPROVE"; at: string }
  | { type: "REJECT"; at: string }
  | { type: "EXPIRE"; at: string }
  | { type: "SUBMISSION_STARTED"; at: string }
  | { type: "BROKER_ACK"; at: string; brokerOrderId: string }
  | { type: "BROKER_STATUS"; at: string; status: "OPEN" | "PARTIAL" | "FILLED" | "CANCELLED" | "REJECTED"; filledQuantity: number }
  | { type: "HALT"; at: string; reason: string };

const terminal: ReadonlySet<OrderPhase> = new Set(["REJECTED", "EXPIRED", "FILLED", "CANCELLED", "BROKER_REJECTED", "HALTED"]);

export function transitionOrder(record: OrderRecord, event: OrderEvent): OrderRecord {
  if (!record.proposalId || !Number.isFinite(Date.parse(record.expiresAt))) throw new Error("Invalid proposal");
  if (!Number.isFinite(Date.parse(event.at))) throw new Error("Invalid event timestamp");
  if (terminal.has(record.phase)) throw new Error("Terminal order cannot transition");
  if (event.type === "HALT") return { ...record, phase: "HALTED", reason: event.reason };
  if (event.type === "EXPIRE") {
    if (record.phase !== "PROPOSED" && record.phase !== "APPROVED") throw new Error("Cannot expire submitted order");
    return { ...record, phase: "EXPIRED" };
  }
  if (event.type === "REJECT") {
    if (record.phase !== "PROPOSED") throw new Error("Cannot reject submitted order");
    return { ...record, phase: "REJECTED" };
  }
  if (event.type === "APPROVE") {
    if (record.phase !== "PROPOSED" || Date.parse(event.at) >= Date.parse(record.expiresAt)) throw new Error("Proposal expired or not pending");
    return { ...record, phase: "APPROVED", approvedAt: event.at };
  }
  if (event.type === "SUBMISSION_STARTED") {
    if (record.phase !== "APPROVED" || Date.parse(event.at) >= Date.parse(record.expiresAt)) throw new Error("Order not approved or expired");
    // UNKNOWN is deliberate: after attempting a send, a timeout must not trigger a retry.
    return { ...record, phase: "SUBMISSION_UNKNOWN" };
  }
  if (event.type === "BROKER_ACK") {
    if (record.phase !== "SUBMISSION_UNKNOWN" || !event.brokerOrderId) throw new Error("Broker acknowledgement not expected");
    return { ...record, phase: "BROKER_ACCEPTED", brokerOrderId: event.brokerOrderId };
  }
  if (event.type === "BROKER_STATUS") {
    if (!["SUBMISSION_UNKNOWN", "BROKER_ACCEPTED", "PARTIALLY_FILLED"].includes(record.phase)) throw new Error("Broker status not expected");
    if (!Number.isInteger(event.filledQuantity) || event.filledQuantity < record.filledQuantity || event.filledQuantity > 1) throw new Error("Invalid fill quantity");
    const phase: OrderPhase = event.status === "FILLED" ? "FILLED"
      : event.status === "PARTIAL" ? "PARTIALLY_FILLED"
      : event.status === "CANCELLED" ? "CANCELLED"
      : event.status === "REJECTED" ? "BROKER_REJECTED"
      : "BROKER_ACCEPTED";
    if (phase === "FILLED" && event.filledQuantity !== 1) throw new Error("Fill status without full quantity");
    return { ...record, phase, filledQuantity: event.filledQuantity };
  }
  throw new Error("Unknown order event");
}
