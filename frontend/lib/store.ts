import { create } from 'zustand';

export interface LogEntry {
  id: number;
  timestamp: string;
  level: string;
  icon: string;
  message: string;
  data: Record<string, unknown>;
}

export interface Position {
  id: string;
  symbol: string;
  direction: string;
  entry_price: number;
  amount_usdt: number;
  stop_loss_price: number;
  take_profit_price: number;
  stop_loss_pct: number;
  take_profit_pct: number;
  confidence: number;
  opened_at: string;
  status: string;
  pnl_usdt: number;
  pnl_pct: number;
}

export interface Prediction {
  symbol?: string;
  direction?: string;
  confidence?: number;
  should_trade?: boolean;
  threshold?: number;
  stop_loss_pct?: number;
  take_profit_pct?: number;
  reasoning?: string[];
  component_scores?: {
    ml_ai?: number;
    technical: number;
    sentiment: number;
    momentum_mtf: number;
    microstructure: number;
    patterns?: number;
  };
  pattern_summary?: Record<string, unknown>;
  direction_votes?: Record<string, number>;
}

export interface TAComposite {
  score: number;
  direction: string;
  bull_signals: number;
  bear_signals: number;
  total_signals: number;
}

export interface Stats {
  total_trades: number;
  wins: number;
  losses: number;
  win_rate_pct: number;
  total_pnl_usdt: number;
  open_positions: number;
  trade_history: Position[];
}

export interface Candle {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface BotState {
  status: string;
  status_message: string;
  symbol: string;
  timeframe: string;
  running: boolean;
  cycle_count: number;
  started_at: string | null;
  confidence_threshold: number;
  exchange: string;
  exchange_connected: boolean;
  paper_mode: boolean;
  last_prediction: Prediction;
  open_positions: Position[];
  stats: Stats;
}

interface Store {
  // Bot state
  botState: BotState;
  setBotState: (s: Partial<BotState>) => void;

  // Logs
  logs: LogEntry[];
  addLog: (log: LogEntry) => void;
  setLogs: (logs: LogEntry[]) => void;

  // Chart candles
  candles: Candle[];
  setCandles: (c: Candle[]) => void;
  addCandle: (c: Candle) => void;

  // Current price
  currentPrice: number;
  setCurrentPrice: (p: number) => void;

  // Prediction / analysis
  prediction: Prediction;
  setPrediction: (p: Prediction) => void;
  taComposite: TAComposite | null;
  setTAComposite: (t: TAComposite) => void;

  // News
  news: Record<string, unknown>;
  setNews: (n: Record<string, unknown>) => void;

  // Positions
  positions: Position[];
  setPositions: (p: Position[]) => void;
  addPosition: (p: Position) => void;
  updatePosition: (p: Position) => void;

  // Stats
  stats: Stats;
  setStats: (s: Stats) => void;

  // UI
  activeTab: string;
  setActiveTab: (t: string) => void;
  wsConnected: boolean;
  setWsConnected: (v: boolean) => void;
}

const defaultBotState: BotState = {
  status: 'idle',
  status_message: 'Bot is idle',
  symbol: 'BTCUSDT.p',
  timeframe: '15m',
  running: false,
  cycle_count: 0,
  started_at: null,
  confidence_threshold: 85,
  exchange: 'binance',
  exchange_connected: false,
  paper_mode: true,
  last_prediction: {},
  open_positions: [],
  stats: { total_trades: 0, wins: 0, losses: 0, win_rate_pct: 0, total_pnl_usdt: 0, open_positions: 0, trade_history: [] },
};

export const useStore = create<Store>((set) => ({
  botState: defaultBotState,
  setBotState: (s) => set((state) => ({ botState: { ...state.botState, ...s } })),

  logs: [],
  addLog: (log) => set((state) => ({ logs: [log, ...state.logs].slice(0, 500) })),
  setLogs: (logs) => set({ logs }),

  candles: [],
  setCandles: (candles) => set({ candles }),
  addCandle: (c) => set((state) => {
    const updated = [...state.candles];
    const idx = updated.findIndex((x) => x.time === c.time);
    if (idx >= 0) updated[idx] = c; else updated.push(c);
    return { candles: updated.slice(-200) };
  }),

  currentPrice: 0,
  setCurrentPrice: (currentPrice) => set({ currentPrice }),

  prediction: {},
  setPrediction: (prediction) => set({ prediction }),
  taComposite: null,
  setTAComposite: (taComposite) => set({ taComposite }),

  news: {},
  setNews: (news) => set({ news }),

  positions: [],
  setPositions: (positions) => set({ positions }),
  addPosition: (p) => set((state) => ({ positions: [p, ...state.positions] })),
  updatePosition: (p) => set((state) => ({
    positions: state.positions.map((x) => (x.id === p.id ? p : x)),
  })),

  stats: defaultBotState.stats,
  setStats: (stats) => set({ stats }),

  activeTab: 'dashboard',
  setActiveTab: (activeTab) => set({ activeTab }),
  wsConnected: false,
  setWsConnected: (wsConnected) => set({ wsConnected }),
}));
