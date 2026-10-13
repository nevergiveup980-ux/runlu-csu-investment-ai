interface Env {
  TWELVE_DATA_API_KEY: string;
  CSU_SYMBOL: string;
  CSU_EXCHANGE: string;
  CSU_SNAPSHOT_TOKEN?: string;
  PRIVATE_PORTFOLIO_USERNAME?: string;
  PRIVATE_PORTFOLIO_PASSWORD_HASH?: string;
  PRIVATE_SESSION_SECRET?: string;
  PRIVATE_PORTFOLIO?: {
    get(key: string): Promise<string | null>;
    put(key: string, value: string, options?: { expirationTtl?: number }): Promise<void>;
    delete(key: string): Promise<void>;
  };
  ASSETS: { fetch(request: Request): Promise<Response> };
}
