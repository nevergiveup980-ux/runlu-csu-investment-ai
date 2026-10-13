export interface PortfolioKV {
  get(key: string): Promise<string | null>;
  put(key: string, value: string, options?: { expirationTtl?: number }): Promise<void>;
  delete(key: string): Promise<void>;
}

export type PrivatePortfolioEnv = {
  PRIVATE_PORTFOLIO?: PortfolioKV;
  PRIVATE_PORTFOLIO_USERNAME?: string;
  PRIVATE_PORTFOLIO_PASSWORD_HASH?: string;
  PRIVATE_PORTFOLIO_PASSWORD_SALT?: string;
  PRIVATE_SESSION_SECRET?: string;
};

export type PrivatePortfolioSnapshot = {
  currency: string;
  cash: number | null;
  buyingPower: number | null;
  estimatedEquity: number | null;
  positions: Array<{
    symbol: string;
    quantity: number;
    averageCost: number | null;
    marketValue: number | null;
  }>;
  openOrderCount: number;
  fetchedAt: string;
};

const enc = new TextEncoder();

function bytesToHex(bytes: Uint8Array): string {
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

function base64Url(bytes: Uint8Array): string {
  let binary = "";
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/g, "");
}

function fromBase64Url(value: string): Uint8Array {
  const padded = value.replace(/-/g, "+").replace(/_/g, "/") + "===".slice((value.length + 3) % 4);
  const raw = atob(padded);
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

export async function sha256Hex(value: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", enc.encode(value));
  return bytesToHex(new Uint8Array(digest));
}

export async function pbkdf2Hex(
  password: string,
  salt: string,
  iterations = 210_000,
): Promise<string> {
  const material = await crypto.subtle.importKey(
    "raw",
    enc.encode(password),
    "PBKDF2",
    false,
    ["deriveBits"],
  );
  const bits = await crypto.subtle.deriveBits(
    {
      name: "PBKDF2",
      hash: "SHA-256",
      salt: enc.encode(salt),
      iterations,
    },
    material,
    256,
  );
  return bytesToHex(new Uint8Array(bits));
}

export function constantTimeEqual(a: string, b: string): boolean {
  const aa = enc.encode(String(a));
  const bb = enc.encode(String(b));
  const length = Math.max(aa.length, bb.length);
  let diff = aa.length ^ bb.length;
  for (let i = 0; i < length; i++) diff |= (aa[i] || 0) ^ (bb[i] || 0);
  return diff === 0;
}

async function hmac(secret: string, value: string): Promise<Uint8Array> {
  const key = await crypto.subtle.importKey(
    "raw",
    enc.encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  return new Uint8Array(await crypto.subtle.sign("HMAC", key, enc.encode(value)));
}

export async function createSessionToken(
  username: string,
  secret: string,
  nowSeconds = Math.floor(Date.now() / 1000),
  ttlSeconds = 8 * 60 * 60,
): Promise<string> {
  const payload = base64Url(enc.encode(JSON.stringify({
    sub: username,
    iat: nowSeconds,
    exp: nowSeconds + ttlSeconds,
    v: 1,
  })));
  const signature = base64Url(await hmac(secret, payload));
  return payload + "." + signature;
}

export async function verifySessionToken(
  token: string,
  username: string,
  secret: string,
  nowSeconds = Math.floor(Date.now() / 1000),
): Promise<boolean> {
  const [payload, signature, extra] = String(token || "").split(".");
  if (!payload || !signature || extra) return false;
  const expected = base64Url(await hmac(secret, payload));
  if (!constantTimeEqual(signature, expected)) return false;
  try {
    const parsed = JSON.parse(new TextDecoder().decode(fromBase64Url(payload)));
    return parsed?.v === 1
      && parsed?.sub === username
      && Number.isFinite(parsed?.iat)
      && Number.isFinite(parsed?.exp)
      && parsed.exp > nowSeconds
      && parsed.iat <= nowSeconds + 60;
  } catch {
    return false;
  }
}

export function getCookie(request: Request, name: string): string | null {
  const raw = request.headers.get("Cookie") || "";
  for (const pair of raw.split(";")) {
    const idx = pair.indexOf("=");
    if (idx < 0) continue;
    if (pair.slice(0, idx).trim() === name) return pair.slice(idx + 1).trim();
  }
  return null;
}

function finiteOrNull(value: unknown): number | null {
  if (value == null || value === "") return null;
  const number = Number(value);
  return Number.isFinite(number) && number >= 0 ? number : null;
}

export function sanitizePrivatePortfolioSnapshot(raw: any): PrivatePortfolioSnapshot {
  const positions = Array.isArray(raw?.positions) ? raw.positions : [];
  const safePositions = positions.slice(0, 100).map((p: any) => ({
    symbol: String(p?.symbol || p?.ticker || "").trim().toUpperCase().slice(0, 32),
    quantity: Math.max(0, Number(p?.quantity ?? p?.units ?? 0) || 0),
    averageCost: finiteOrNull(p?.averageCost ?? p?.average_cost),
    marketValue: finiteOrNull(p?.marketValue ?? p?.market_value),
  })).filter((p: any) => p.symbol);

  const cash = finiteOrNull(raw?.cash);
  const buyingPower = finiteOrNull(raw?.buyingPower ?? raw?.buying_power);
  const positionValue = safePositions.reduce((sum: number, p: any) => sum + (p.marketValue || 0), 0);
  const fetchedAt = String(raw?.fetchedAt || raw?.fetched_at || "");
  const parsedTime = Date.parse(fetchedAt);
  if (!Number.isFinite(parsedTime)) throw new Error("Private portfolio snapshot requires a valid fetchedAt timestamp");

  return {
    currency: String(raw?.currency || "CAD").toUpperCase().slice(0, 8),
    cash,
    buyingPower,
    estimatedEquity: cash == null ? (positionValue || null) : cash + positionValue,
    positions: safePositions,
    openOrderCount: Math.min(
      1000,
      Array.isArray(raw?.openOrders) ? raw.openOrders.length : Array.isArray(raw?.orders) ? raw.orders.length : 0,
    ),
    fetchedAt: new Date(parsedTime).toISOString(),
  };
}

export async function verifyPrivateLogin(
  username: string,
  password: string,
  env: PrivatePortfolioEnv,
): Promise<boolean> {
  const expectedUser = String(env.PRIVATE_PORTFOLIO_USERNAME || "");
  const expectedHash = String(env.PRIVATE_PORTFOLIO_PASSWORD_HASH || "").toLowerCase();
  const salt = String(env.PRIVATE_PORTFOLIO_PASSWORD_SALT || "");
  if (!expectedUser || !salt || !/^[a-f0-9]{64}$/.test(expectedHash)) return false;
  const actualHash = await pbkdf2Hex(String(password || ""), salt);
  return constantTimeEqual(String(username || ""), expectedUser)
    && constantTimeEqual(actualHash, expectedHash);
}

export function privatePortfolioConfigured(env: PrivatePortfolioEnv): boolean {
  return Boolean(
    env.PRIVATE_PORTFOLIO
    && env.PRIVATE_PORTFOLIO_USERNAME
    && env.PRIVATE_PORTFOLIO_PASSWORD_HASH
    && env.PRIVATE_PORTFOLIO_PASSWORD_SALT
    && env.PRIVATE_SESSION_SECRET,
  );
}
