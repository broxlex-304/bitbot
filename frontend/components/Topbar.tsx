'use client';
import { useStore } from '@/lib/store';
import { api } from '@/lib/api';
import { useState, useEffect } from 'react';

export default function Topbar() {
  const { botState, currentPrice, wsConnected, setBotState } = useStore();
  const [loading, setLoading] = useState(false);
  const DEFAULT_SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT', 'ADA/USDT', 'DOGE/USDT', 'AVAX/USDT', 'DOT/USDT', 'MATIC/USDT'];
  const [symbolsList, setSymbolsList] = useState<{symbol: string, label: string}[]>(
    DEFAULT_SYMBOLS.map(s => ({symbol: s, label: s}))
  );

  useEffect(() => {
    const fetchDropdownData = async () => {
      try {
        const [symRes, scanRes] = await Promise.all([
          api.getSymbols().catch(() => ({ symbols: [] })),
          api.getScannerResults().catch(() => ({ results: [] }))
        ]);

        let baseSymbols = symRes.symbols && symRes.symbols.length > 0 ? symRes.symbols : DEFAULT_SYMBOLS;
        let newList: {symbol: string, label: string}[] = [];
        const scannedSet = new Set<string>();

        if (scanRes.results && scanRes.results.length > 0) {
          scanRes.results.forEach((r: any) => {
            scannedSet.add(r.symbol);
            const icon = r.direction === 'BUY' ? '🟢' : r.direction === 'SELL' ? '🔴' : '⚪';
            newList.push({
              symbol: r.symbol,
              label: `${icon} ${r.symbol} - ${r.confidence.toFixed(1)}%`
            });
          });
        }

        // Append the rest alphabetically
        baseSymbols.forEach((s: string) => {
          if (!scannedSet.has(s)) {
            newList.push({ symbol: s, label: s });
          }
        });

        setSymbolsList(newList);
      } catch (e) {}
    };

    fetchDropdownData();
    const interval = setInterval(fetchDropdownData, 30000); // refresh scanner data every 30s
    return () => clearInterval(interval);
  }, [botState.exchange_connected]);

  const handleStart = async () => {
    setLoading(true);
    try { await api.start(botState.symbol, botState.timeframe); } finally { setLoading(false); }
  };
  const handleStop = async () => {
    setLoading(true);
    try { await api.stop(); } finally { setLoading(false); }
  };

  const handleSymbolChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const newSymbol = e.target.value.toUpperCase();
    setBotState({ symbol: newSymbol });
    try {
      await api.updateSettings({ symbol: newSymbol });
      api.analyzeNow();
    } catch (err) { console.error(err); }
  };

  const statusColor: Record<string, string> = {
    running: 'var(--green)', analyzing: 'var(--yellow)', waiting: 'var(--primary)',
    idle: 'var(--text-muted)', paused: 'var(--yellow)', error: 'var(--red)',
  };

  return (
    <header className="topbar">
      {/* Symbol + price */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <select
          className="input-field" 
          value={botState.symbol} 
          onChange={(e: React.ChangeEvent<HTMLSelectElement>) => handleSymbolChange(e as any)}
          style={{ width: 190, fontWeight: 800, padding: '4px 8px', height: 32 }}
        >
          {symbolsList.map(s => <option key={s.symbol} value={s.symbol}>{s.label}</option>)}
        </select>
        
        {currentPrice > 0 && (
          <div style={{ fontSize: 15, fontWeight: 700, fontFamily: 'JetBrains Mono, monospace', color: 'var(--green)' }}>
            ${currentPrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        )}
        <span className="badge badge-gray" style={{ fontSize: 11 }}>{botState.timeframe}</span>
      </div>

      {/* Status */}
      <div style={{ flex: 1, display: 'flex', alignItems: 'center', gap: 8 }}>
        <span className={`status-dot ${botState.status}`} />
        <span style={{ fontSize: 12, color: statusColor[botState.status] || 'var(--text-muted)', maxWidth: 360, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {botState.status_message}
        </span>
      </div>

      {/* Controls */}
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        {!wsConnected && (
          <span className="badge badge-red">No WS</span>
        )}
        {botState.paper_mode && (
          <span className="badge badge-yellow" style={{ fontSize: 11 }}>📝 Paper Mode</span>
        )}
        {botState.running ? (
          <button className="btn btn-red btn-sm" onClick={handleStop} disabled={loading}>
            ⏹ Stop
          </button>
        ) : (
          <button className="btn btn-green btn-sm" onClick={handleStart} disabled={loading}>
            ▶ Start
          </button>
        )}
        {botState.running && (
          <button className="btn btn-ghost btn-sm" onClick={() => api.analyzeNow()}>
            🔄 Analyze Now
          </button>
        )}
      </div>
    </header>
  );
}
