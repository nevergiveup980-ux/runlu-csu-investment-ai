import {
  constantTimeEqual,
  createSessionToken,
  pbkdf2Hex,
  privatePortfolioConfigured,
  sanitizePrivatePortfolioSnapshot,
  verifyPrivateLogin,
  verifySessionToken,
} from "./private-portfolio";

const expect = (condition: unknown, message: string) => {
  if (!condition) throw new Error(message);
};

const password = "synthetic-strong-password";
const passwordSalt = "synthetic-random-salt";
const passwordHash = await pbkdf2Hex(password, passwordSalt);
const env = {
  PRIVATE_PORTFOLIO: {
    async get() { return null; },
    async put() {},
    async delete() {},
  },
  PRIVATE_PORTFOLIO_USERNAME: "john",
  PRIVATE_PORTFOLIO_PASSWORD_HASH: passwordHash,
  PRIVATE_PORTFOLIO_PASSWORD_SALT: passwordSalt,
  PRIVATE_SESSION_SECRET: "synthetic-session-secret-with-length",
};

expect(privatePortfolioConfigured(env), "private portfolio should report configured");
expect(await verifyPrivateLogin("john", password, env), "valid private login should pass");
expect(!(await verifyPrivateLogin("john", "wrong", env)), "wrong password must fail");
expect(!(await verifyPrivateLogin("wrong", password, env)), "wrong username must fail");
expect(constantTimeEqual("abc", "abc"), "constant comparison should accept equal values");
expect(!constantTimeEqual("abc", "abd"), "constant comparison should reject different values");

const token = await createSessionToken("john", env.PRIVATE_SESSION_SECRET, 1000, 60);
expect(await verifySessionToken(token, "john", env.PRIVATE_SESSION_SECRET, 1030), "valid session token should pass");
expect(!(await verifySessionToken(token, "john", env.PRIVATE_SESSION_SECRET, 1061)), "expired session must fail");
expect(!(await verifySessionToken(token + "x", "john", env.PRIVATE_SESSION_SECRET, 1030)), "tampered session must fail");
expect(!(await verifySessionToken(token, "other", env.PRIVATE_SESSION_SECRET, 1030)), "session subject must match");

const safe = sanitizePrivatePortfolioSnapshot({
  provider: "synthetic",
  accountId: "DO-NOT-PUBLISH",
  clientSecret: "DO-NOT-PUBLISH",
  accessToken: "DO-NOT-PUBLISH",
  currency: "cad",
  cash: 2500,
  buyingPower: 2000,
  fetchedAt: "2026-10-13T11:30:00Z",
  positions: [{
    ticker: "csu.to",
    units: 2,
    average_cost: 2700,
    market_value: 5600,
    secretField: "drop",
  }],
  orders: [{ id: "private-order-id" }],
  transactions: [{ id: "private-history" }],
});
expect(safe.currency === "CAD", "currency should normalize");
expect(safe.cash === 2500, "cash should be retained");
expect(safe.buyingPower === 2000, "buying power should be retained");
expect(safe.positions.length === 1 && safe.positions[0].symbol === "CSU.TO", "holding should be retained");
expect(safe.openOrderCount === 1, "only open-order count should be retained");
expect(safe.estimatedEquity === 8100, "estimated equity should be derived from safe fields");
const serialized = JSON.stringify(safe);
for (const forbidden of ["accountId", "clientSecret", "accessToken", "transactions", "private-order-id", "secretField"]) {
  expect(!serialized.includes(forbidden), "sanitized portfolio leaked forbidden field: " + forbidden);
}

let blocked = false;
try {
  sanitizePrivatePortfolioSnapshot({ cash: 1, fetchedAt: "not-a-time" });
} catch {
  blocked = true;
}
expect(blocked, "invalid snapshot timestamp must fail closed");

console.log("private-portfolio safety tests passed");
