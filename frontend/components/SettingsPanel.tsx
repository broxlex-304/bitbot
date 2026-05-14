'use client';
import { useState, useEffect } from 'react';
import { api } from '@/lib/api';
import { useStore } from '@/lib/store';

const EXCHANGES = ['mexc', 'binance', 'bybit', 'okx', 'kucoin', 'gate', 'bitget', 'huobi'];
const TIMEFRAMES = ['1m', '5m', '15m', '30m', '1h', '4h', '1d'];
const DEFAULT_SYMBOLS = ['BTCUSDT.p', 'BTCUSDT', 'BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'XRP/USDT', 'ADA/USDT', 'DOGE/USDT', 'AVAX/USDT', 'DOT/USDT', 'MATIC/USDT'];

export default function SettingsPanel() {
  const { botState } = useStore();
  const [form, setForm] = useState({
    exchange_id: 'mexc',
    api_key: '',
    api_secret: '',
    symbol: 'BTCUSDT.p',
    timeframe: '15m',
    confidence_threshold: 85,
    trade_amount_usdt: 10,
    stop_loss_percent: 2,
    take_profit_percent: 4,
    max_open_trades: 3,
  });
  const [connecting, setConnecting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState('');
  const [symbolsList, setSymbolsList] = useState<string[]>(DEFAULT_SYMBOLS);

  useEffect(() => {
    api.getSettings().then((s) => {
      setForm((prev) => ({
        ...prev,
        symbol: (s.symbol as string) || prev.symbol,
        timeframe: (s.timeframe as string) || prev.timeframe,
        confidence_threshold: (s.confidence_threshold as number) || prev.confidence_threshold,
        trade_amount_usdt: (s.trade_amount_usdt as number) || prev.trade_amount_usdt,
        stop_loss_percent: (s.stop_loss_percent as number) || prev.stop_loss_percent,
        take_profit_percent: (s.take_profit_percent as number) || prev.take_profit_percent,
        max_open_trades: (s.max_open_trades as number) || prev.max_open_trades,
        exchange_id: (s.exchange_id as string) || prev.exchange_id,
      }));
    }).catch(() => {});
    
    // Fetch dynamic symbols list
    api.getSymbols().then((data) => {
      if (data.symbols && data.symbols.length > 0) {
        const combined = Array.from(new Set([...DEFAULT_SYMBOLS, ...data.symbols]));
        setSymbolsList(combined);
      }
    }).catch(() => {});
  }, [botState.exchange_connected]);

  const handleConnect = async () => {
    setConnecting(true);
    setMsg('');
    try {
      const res = await api.connectExchange(form.exchange_id, form.api_key, form.api_secret) as Record<string,any>;
      if (res.success) {
        setMsg(`✅ ${res.message || 'Connected'}`);
      } else {
        setMsg(`❌ ${res.message || 'Connection failed'}`);
      }
      // Refresh symbols upon connection
      if (res.success) {
        api.getSymbols().then((data) => {
          if (data.symbols && data.symbols.length > 0) setSymbolsList(data.symbols);
        }).catch(() => {});
      }
    } catch { setMsg('❌ Connection error'); }
    finally { setConnecting(false); }
  };

  const handleSave = async () => {
    setSaving(true);
    setMsg('');
    try {
      await api.updateSettings({
        symbol: form.symbol,
        timeframe: form.timeframe,
        confidence_threshold: form.confidence_threshold,
        trade_amount_usdt: form.trade_amount_usdt,
        stop_loss_percent: form.stop_loss_percent,
        take_profit_percent: form.take_profit_percent,
        max_open_trades: form.max_open_trades,
      });
      setMsg('✅ Settings saved');
    } catch { setMsg('❌ Failed to save settings'); }
    finally { setSaving(false); }
  };

  const F = (field: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setForm((prev) => ({ ...prev, [field]: e.target.type === 'number' ? Number(e.target.value) : e.target.value }));

  return (
    <div className="animate-in" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      {/* Exchange Connection */}
      <div className="card">
        <div className="card-title">🔗 Exchange Connection</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 14 }}>
          <div className="input-group" style={{ gridColumn: '1/-1' }}>
            <label className="input-label">Exchange</label>
            <select className="input-field" value={form.exchange_id} onChange={F('exchange_id')}>
              {EXCHANGES.map(e => <option key={e} value={e}>{e.toUpperCase()}</option>)}
            </select>
          </div>
          <div className="input-group">
            <label className="input-label">API Key</label>
            <input className="input-field" type="password" placeholder="Your API key" value={form.api_key} onChange={F('api_key')} />
          </div>
          <div className="input-group">
            <label className="input-label">API Secret</label>
            <input className="input-field" type="password" placeholder="Your API secret" value={form.api_secret} onChange={F('api_secret')} />
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button className="btn btn-primary" onClick={handleConnect} disabled={connecting}>
            {connecting ? '⏳ Connecting...' : '🔌 Connect Exchange'}
          </button>
          <span className={`badge ${botState.exchange_connected ? (botState.paper_mode ? 'badge-yellow' : 'badge-gray') : 'badge-gray'}`} 
                style={{ background: botState.exchange_connected && !botState.paper_mode ? 'var(--green)' : undefined }}>
            {botState.exchange_connected 
              ? (botState.paper_mode ? '● Public (Paper Mode)' : '● MEXC Wallet (Live)') 
              : '○ Disconnected'}
          </span>
          {msg && !saving && <span style={{ fontSize: 13, color: msg.startsWith('✅') ? 'var(--green)' : 'var(--red)', fontWeight: 500 }}>{msg}</span>}
        </div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 8 }}>
          💡 No API keys? The bot runs in <strong style={{ color: 'var(--yellow)' }}>Paper Trade</strong> mode (analysis only, no real orders).
        </div>
      </div>

      {/* Trading Settings */}
      <div className="card">
        <div className="card-title">⚙️ Trading Configuration</div>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 16 }}>
          <div className="input-group">
            <label className="input-label">Symbol</label>
            <select className="input-field" value={form.symbol} onChange={F('symbol')}>
              {symbolsList.map(s => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div className="input-group">
            <label className="input-label">Timeframe</label>
            <select className="input-field" value={form.timeframe} onChange={F('timeframe')}>
              {TIMEFRAMES.map(t => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div className="input-group">
            <label className="input-label">Trade Amount (USDT)</label>
            <input className="input-field" type="number" min="1" value={form.trade_amount_usdt} onChange={F('trade_amount_usdt')} />
          </div>
          <div className="input-group">
            <label className="input-label">Max Open Trades</label>
            <input className="input-field" type="number" min="1" max="10" value={form.max_open_trades} onChange={F('max_open_trades')} />
          </div>
        </div>

        {/* Confidence threshold */}
        <div style={{ marginBottom: 16 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
            <label className="input-label">Confidence Threshold</label>
            <span style={{ fontSize: 14, fontWeight: 700, color: 'var(--primary)', fontFamily: 'JetBrains Mono, monospace' }}>{form.confidence_threshold}%</span>
          </div>
          <input type="range" min="60" max="97" value={form.confidence_threshold} onChange={F('confidence_threshold')}
            style={{ width: '100%', accentColor: 'var(--primary)' }} />
          <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
            <span>60% (Aggressive)</span>
            <span>97% (Ultra-safe)</span>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14, marginBottom: 16 }}>
          <div className="input-group">
            <label className="input-label">Stop Loss %</label>
            <input className="input-field" type="number" step="0.1" min="0.5" max="10" value={form.stop_loss_percent} onChange={F('stop_loss_percent')} />
          </div>
          <div className="input-group">
            <label className="input-label">Take Profit %</label>
            <input className="input-field" type="number" step="0.1" min="0.5" max="20" value={form.take_profit_percent} onChange={F('take_profit_percent')} />
          </div>
        </div>

        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <button className="btn btn-primary" onClick={handleSave} disabled={saving}>
            {saving ? '⏳ Saving...' : '💾 Save Settings'}
          </button>
          {msg && <span style={{ fontSize: 13, color: msg.startsWith('✅') ? 'var(--green)' : 'var(--red)' }}>{msg}</span>}
        </div>
      </div>

      {/* Risk warning */}
      <div style={{ background: 'rgba(245,158,11,0.08)', border: '1px solid rgba(245,158,11,0.2)', borderRadius: 'var(--radius-md)', padding: 14 }}>
        <div style={{ fontSize: 13, color: 'var(--yellow)', fontWeight: 600, marginBottom: 6 }}>⚠️ Risk Disclaimer</div>
        <div style={{ fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          Crypto trading carries significant risk. Past performance does not guarantee future results.
          Only trade with funds you can afford to lose. BitBot is a tool, not financial advice.
          Always monitor your positions.
        </div>
      </div>
    </div>
  );
}
