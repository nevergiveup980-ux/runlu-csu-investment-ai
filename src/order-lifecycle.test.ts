import { transitionOrder, type OrderRecord } from "./order-lifecycle";

const now = new Date();
const start = now.toISOString();
const expiresAt = new Date(now.getTime() + 60_000).toISOString();
const base: OrderRecord = {
  proposalId: "synthetic-test-only", phase: "PROPOSED", createdAt: start,
  expiresAt, filledQuantity: 0, requestedQuantity: 1,
};
const approved = transitionOrder(base, { type: "APPROVE", at: start });
const attempted = transitionOrder(approved, { type: "SUBMISSION_STARTED", at: start });
if (attempted.phase !== "SUBMISSION_UNKNOWN") throw new Error("Submission did not enter unknown state");
let rejectedRetry = false;
try { transitionOrder(attempted, { type: "SUBMISSION_STARTED", at: start }); }
catch { rejectedRetry = true; }
if (!rejectedRetry) throw new Error("Duplicate submission attempt allowed");
const ack = transitionOrder(attempted, { type: "BROKER_ACK", at: start, brokerOrderId: "synthetic-order" });
const filled = transitionOrder(ack, { type: "BROKER_STATUS", at: start, status: "FILLED", filledQuantity: 1 });
if (filled.phase !== "FILLED") throw new Error("Broker fill reconciliation failed");
let rejectedTerminal = false;
try { transitionOrder(filled, { type: "APPROVE", at: start }); }
catch { rejectedTerminal = true; }
if (!rejectedTerminal) throw new Error("Terminal state allowed transition");
console.log("order lifecycle checks passed");
