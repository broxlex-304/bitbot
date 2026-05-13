const API = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(err || res.statusText);
  }
  return res.json();
}

export const api = {
  // Status
  getStatus: () => request<Record<string, unknown>>('/api/status'),
  getLogs: (limit = 100) => request<{ logs: unknown[] }>(`/api/logs?limit=${limit}`),
  getStats: () => request<Record<string, unknown>>('/api/stats'),

  // Bot control
  start: (symbol?: string, timeframe?: string) =>
    request('/api/bot/start', { method: 'POST', body: JSON.stringify({ symbol, timeframe }) }),
  stop: () => request('/api/bot/stop', { method: 'POST', body: '{}' }),
  pause: () => request('/api/bot/pause', { method: 'POST', body: '{}' }),
  resume: () => request('/api/bot/resume', { method: 'POST', body: '{}' }),
  analyzeNow: () => request('/api/bot/analyze-now', { method: 'POST', body: '{}' }),

  // Settings
  getSettings: () => request<Record<string, unknown>>('/api/settings'),
  updateSettings: (data: Record<string, unknown>) =>
    request('/api/settings', { method: 'POST', body: JSON.stringify(data) }),

  // Exchange
  connectExchange: (exchange_id: string, api_key: string, api_secret: string) =>
    request('/api/exchange/connect', {
      method: 'POST',
      body: JSON.stringify({ exchange_id, api_key, api_secret }),
    }),
  getBalance: () => request<Record<string, number>>('/api/exchange/balance'),
  getTicker: (symbol: string) =>
    request<Record<string, unknown>>(`/api/exchange/ticker/${symbol.replace('/', '-')}`),
  getCandles: (symbol: string, timeframe = '15m', limit = 100) =>
    request<unknown[]>(`/api/exchange/candles/${symbol.replace('/', '-')}?timeframe=${timeframe}&limit=${limit}`),
  getSupportedExchanges: () => request<{ exchanges: string[] }>('/api/exchange/supported'),
  getSymbols: () => request<{ symbols: string[] }>('/api/exchange/symbols'),

  // Positions
  getPositions: () => request<{ open: unknown[]; history: unknown[] }>('/api/positions'),
  closePosition: (position_id: string) =>
    request('/api/positions/close', { method: 'POST', body: JSON.stringify({ position_id }) }),

  // Prediction
  getPrediction: () => request<Record<string, unknown>>('/api/bot/prediction'),

  // Scanner
  getScannerResults: () => request<{ results: any[] }>('/api/scanner'),
};
