interface Env {
  TWELVE_DATA_API_KEY: string;
  CSU_SYMBOL: string;
  CSU_EXCHANGE: string;
  ASSETS: { fetch(request: Request): Promise<Response> };
}
