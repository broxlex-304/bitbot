'use client';
import { useWebSocket } from '@/lib/useWebSocket';
import { useStore } from '@/lib/store';
import { useEffect } from 'react';
import { api } from '@/lib/api';
import Sidebar from '@/components/Sidebar';
import Topbar from '@/components/Topbar';
import TradingChart from '@/components/TradingChart';
import PredictionPanel from '@/components/PredictionPanel';
import LogFeed from '@/components/LogFeed';
import PositionsPanel from '@/components/PositionsPanel';
import SettingsPanel from '@/components/SettingsPanel';

/* ─── Stat Card ─────────────────────────────────────────────────────────────── */
function StatCard({ label, value, sub, accent, icon }: {
  label: string; value: string | number; sub?: string; accent?: string; icon?: string;
}) {
  return (
    <div className="stat-card" style={{ '--accent': accent || 'var(--primary)' } as React.CSSProperties}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div className="stat-label">{label}</div>
        {icon && <span style={{ fontSize: 20, opacity: 0.7 }}>{icon}</span>}
      </div>
      <div className="stat-value">{value}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

/* ─── News Card (top-level, no duplicate) ────────────────────────────────────── */
function NewsCard() {
  const { news } = useStore();
  const n = news as Record<string, unknown>;

  if (!n.sentiment) {
    return (
      <div className="card" style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '40px 20px', fontSize: 13 }}>
        📰 Start the bot to fetch live news & sentiment
      </div>
    );
  }

  const articles = (n.articles as Array<{ source: string; title: string; score: number }>) || [];
  const fg = n.fear_greed as Record<string, unknown> | undefined;

  return (
    <div className="card animate-in">
      <div className="card-title">📰 Live News & Sentiment</div>
      <div style={{ display: 'flex', gap: 12, marginBottom: 16 }}>
        <div style={{ flex: 1, textAlign: 'center', padding: 14, background: 'var(--bg-base)', borderRadius: 'var(--radius-md)' }}>
          <div style={{
            fontSize: 22, fontWeight: 800,
            color: n.sentiment === 'POSITIVE' ? 'var(--green)' : n.sentiment === 'NEGATIVE' ? 'var(--red)' : 'var(--yellow)',
          }}>
            {String(n.sentiment)}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>Market Mood</div>
        </div>
        {fg && (
          <div style={{ flex: 1, textAlign: 'center', padding: 14, background: 'var(--bg-base)', borderRadius: 'var(--radius-md)' }}>
            <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--primary)' }}>{String(fg.value)}</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>{String(fg.classification)}</div>
          </div>
        )}
        <div style={{ flex: 1, textAlign: 'center', padding: 14, background: 'var(--bg-base)', borderRadius: 'var(--radius-md)' }}>
          <div style={{ fontSize: 22, fontWeight: 800, color: 'var(--cyan)' }}>{String(n.article_count || 0)}</div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>Articles</div>
        </div>
      </div>

      {articles.map((a, i) => (
        <div key={`article-${i}`} style={{ padding: '10px 0', borderBottom: '1px solid var(--border)' }}>
          <div style={{ color: 'var(--text-primary)', fontSize: 12, marginBottom: 6, lineHeight: 1.5 }}>{a.title}</div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span className="badge badge-gray" style={{ fontSize: 10 }}>{a.source}</span>
            <span style={{ color: a.score > 0 ? 'var(--green)' : a.score < 0 ? 'var(--red)' : 'var(--yellow)', fontSize: 12, fontWeight: 600, fontFamily: 'JetBrains Mono, monospace' }}>
              {a.score > 0 ? '▲' : a.score < 0 ? '▼' : '→'} {Math.abs(a.score).toFixed(2)}
            </span>
          </div>
        </div>
      ))}

      {!!n.trending && (
        <div style={{ marginTop: 12 }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 6 }}>🔥 Trending Coins</div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {(n.trending as string[]).map((t) => (
              <span key={`trend-${t}`} className="badge badge-purple" style={{ fontSize: 10 }}>{t}</span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* ─── Indicators Card ────────────────────────────────────────────────────────── */
function IndicatorsCard() {
  const { prediction } = useStore();
  const scores = prediction.component_scores;

  if (!scores) {
    return (
      <div className="card" style={{ textAlign: 'center', color: 'var(--text-muted)', padding: '36px 20px', fontSize: 13 }}>
        📊 Start the bot to see indicator readings
      </div>
    );
  }

  const votes = prediction.direction_votes || {};
  const ps = prediction.pattern_summary;

  return (
    <div className="card animate-in">
      <div className="card-title">📊 Signal Intelligence</div>

      {/* Vote boxes */}
      <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
        {[
          { label: 'BUY', count: votes.BUY || 0, color: 'var(--green)', bg: 'rgba(16,185,129,0.1)' },
          { label: 'SELL', count: votes.SELL || 0, color: 'var(--red)', bg: 'rgba(239,68,68,0.1)' },
          { label: 'NEUTRAL', count: votes.NEUTRAL || 0, color: 'var(--yellow)', bg: 'rgba(245,158,11,0.1)' },
        ].map((v) => (
          <div key={v.label} style={{ flex: 1, textAlign: 'center', padding: '10px 6px', background: v.bg, borderRadius: 'var(--radius-sm)', border: `1px solid ${v.color}30` }}>
            <div style={{ fontSize: 22, fontWeight: 800, color: v.color }}>{v.count}</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{v.label}</div>
          </div>
        ))}
      </div>

      {/* Score bars */}
      {[
        { name: 'ML Random Forest', value: scores.ml_ai ?? 50, color: 'var(--blue)' },
        { name: 'Technical (20+ indicators)', value: scores.technical, color: 'var(--primary)' },
        { name: 'Advanced Patterns', value: scores.patterns ?? 50, color: 'var(--cyan)' },
        { name: 'News Sentiment', value: scores.sentiment, color: 'var(--purple)' },
        { name: 'Multi-Timeframe MTF', value: scores.momentum_mtf, color: 'var(--green)' },
        { name: 'Order Book Depth', value: scores.microstructure, color: 'var(--yellow)' },
      ].map((s) => (
        <div key={s.name} className="indicator-row">
          <span className="ind-name">{s.name}</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <div style={{ width: 90, height: 4, background: 'rgba(255,255,255,0.06)', borderRadius: 2, overflow: 'hidden' }}>
              <div style={{ width: `${s.value}%`, height: '100%', background: s.color, borderRadius: 2, transition: 'width 0.8s ease', boxShadow: `0 0 6px ${s.color}60` }} />
            </div>
            <span className="ind-value" style={{ color: s.color, minWidth: 36 }}>{s.value.toFixed(0)}%</span>
          </div>
        </div>
      ))}

      {/* Pattern Summary */}
      {!!ps?.regime && (
        <>
          <div className="divider" />
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.07em' }}>Advanced Patterns</div>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, fontSize: 12 }}>
            {[
              { label: 'Market Regime', value: String(ps.regime) },
              { label: 'ADX Strength', value: `${Number(ps.adx).toFixed(1)}`, color: Number(ps.adx) > 25 ? 'var(--green)' : 'var(--yellow)' },
              { label: 'Fib Support', value: ps.at_fib_support ? '✅ YES' : '—', color: ps.at_fib_support ? 'var(--green)' : undefined },
              { label: 'Fib Resistance', value: ps.at_fib_resistance ? '⚠️ YES' : '—', color: ps.at_fib_resistance ? 'var(--red)' : undefined },
              { label: 'Bull Divergence', value: ps.bullish_div ? '🟢 YES' : '—', color: ps.bullish_div ? 'var(--green)' : undefined },
              { label: 'Bear Divergence', value: ps.bearish_div ? '🔴 YES' : '—', color: ps.bearish_div ? 'var(--red)' : undefined },
            ].map((item) => (
              <div key={item.label} style={{ background: 'var(--bg-base)', padding: '8px 10px', borderRadius: 'var(--radius-sm)' }}>
                <div style={{ color: 'var(--text-muted)', fontSize: 10, marginBottom: 3 }}>{item.label}</div>
                <div style={{ fontWeight: 600, color: item.color || 'var(--text-primary)', fontSize: 12 }}>{item.value}</div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}

/* ─── Dashboard View ─────────────────────────────────────────────────────────── */
function Dashboard() {
  const { botState, currentPrice } = useStore();
  const stats = botState.stats || {};
  const pnlColor = (stats.total_pnl_usdt || 0) >= 0 ? 'var(--green)' : 'var(--red)';

  return (
    <div className="animate-in" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
      <div className="grid-4">
        <StatCard
          label="Current Price"
          value={currentPrice > 0 ? `$${currentPrice.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—'}
          sub={botState.symbol}
          accent="var(--primary)" icon="💲"
        />
        <StatCard
          label="Total P&L"
          value={(stats.total_pnl_usdt || 0) >= 0 ? `+$${(stats.total_pnl_usdt || 0).toFixed(2)}` : `-$${Math.abs(stats.total_pnl_usdt || 0).toFixed(2)}`}
          sub={`${stats.total_trades || 0} trades`}
          accent={pnlColor} icon="💰"
        />
        <StatCard
          label="Win Rate"
          value={`${(stats.win_rate_pct || 0).toFixed(1)}%`}
          sub={`${stats.wins || 0}W / ${stats.losses || 0}L`}
          accent="var(--green)" icon="🏆"
        />
        <StatCard
          label="Open Positions"
          value={stats.open_positions || 0}
          sub={`Threshold: ${botState.confidence_threshold ?? 85}%`}
          accent="var(--purple)" icon="📂"
        />
      </div>

      <div className="grid-main">
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <TradingChart />
          <IndicatorsCard />
          <NewsCard />
        </div>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <PredictionPanel />
          <div className="card">
            <div className="card-title">📋 Live Activity</div>
            <LogFeed maxHeight="260px" />
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── Signals View ───────────────────────────────────────────────────────────── */
function SignalsView() {
  const { prediction, taComposite } = useStore();
  return (
    <div className="animate-in" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
      <PredictionPanel />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
        {taComposite && (
          <div className="card">
            <div className="card-title">📊 TA Score</div>
            <div style={{ textAlign: 'center', padding: '16px 0' }}>
              <div style={{ fontSize: 52, fontWeight: 900, color: taComposite.score >= 60 ? 'var(--green)' : taComposite.score <= 40 ? 'var(--red)' : 'var(--yellow)' }}>
                {taComposite.score.toFixed(0)}%
              </div>
              <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>{taComposite.direction} — {taComposite.total_signals} signals</div>
            </div>
            <div style={{ display: 'flex', gap: 10 }}>
              {[
                { l: '▲ Bullish', v: taComposite.bull_signals, c: 'var(--green)' },
                { l: '▼ Bearish', v: taComposite.bear_signals, c: 'var(--red)' },
              ].map((x) => (
                <div key={x.l} style={{ flex: 1, textAlign: 'center', padding: 12, background: 'var(--bg-base)', borderRadius: 'var(--radius-sm)' }}>
                  <div style={{ fontSize: 22, fontWeight: 800, color: x.c }}>{x.v}</div>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>{x.l}</div>
                </div>
              ))}
            </div>
          </div>
        )}
        <div className="card">
          <div className="card-title">🎯 Trade Parameters</div>
          {prediction.stop_loss_pct ? (
            [
              { label: 'Direction', value: prediction.direction || '—', color: prediction.direction === 'BUY' ? 'var(--green)' : prediction.direction === 'SELL' ? 'var(--red)' : 'var(--yellow)' },
              { label: 'Confidence', value: `${prediction.confidence}%`, color: 'var(--primary)' },
              { label: 'Stop Loss', value: `-${prediction.stop_loss_pct}%`, color: 'var(--red)' },
              { label: 'Take Profit', value: `+${prediction.take_profit_pct}%`, color: 'var(--green)' },
              { label: 'Risk:Reward', value: `1:${((prediction.take_profit_pct! / prediction.stop_loss_pct!)).toFixed(1)}`, color: 'var(--yellow)' },
              { label: 'Threshold', value: `${prediction.threshold ?? 85}%`, color: 'var(--text-muted)' },
            ].map((r) => (
              <div key={r.label} className="indicator-row">
                <span className="ind-name">{r.label}</span>
                <span className="ind-value" style={{ color: r.color, fontSize: 14 }}>{r.value}</span>
              </div>
            ))
          ) : (
            <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '20px 0', fontSize: 13 }}>No active signal</div>
          )}
        </div>
        <div className="card">
          <div className="card-title">💡 Bot Reasoning</div>
          {prediction.reasoning && prediction.reasoning.length > 0 ? (
            prediction.reasoning.map((r, i) => (
              <div key={`reason-${i}`} style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 8, display: 'flex', gap: 6 }}>
                <span style={{ color: 'var(--primary)', flexShrink: 0 }}>›</span>{r}
              </div>
            ))
          ) : (
            <div style={{ color: 'var(--text-muted)', fontSize: 12 }}>No reasoning available yet</div>
          )}
        </div>
      </div>
    </div>
  );
}

/* ─── Logs View ──────────────────────────────────────────────────────────────── */
function LogsView() {
  return (
    <div className="animate-in">
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 }}>
          <div className="card-title" style={{ margin: 0 }}>📋 Full Activity Log</div>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Last 500 entries · newest first</span>
        </div>
        <LogFeed maxHeight="calc(100vh - 180px)" />
      </div>
    </div>
  );
}

/* ─── Page ───────────────────────────────────────────────────────────────────── */
export default function Page() {
  useWebSocket();
  const { activeTab, botState, setCandles, setCurrentPrice } = useStore();

  // Load initial candles and price on mount / when symbol changes
  useEffect(() => {
    const sym = botState.symbol;
    const tf  = botState.timeframe;
    api.getCandles(sym, tf, 150)
      .then((data) => { if (Array.isArray(data) && data.length > 0) setCandles(data as Parameters<typeof setCandles>[0]); })
      .catch(() => {});
    api.getTicker(sym)
      .then((t) => { const p = (t as Record<string, unknown>).last; if (p) setCurrentPrice(Number(p)); })
      .catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [botState.symbol, botState.timeframe]);

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard': return <Dashboard />;
      case 'chart':     return <div className="animate-in"><TradingChart /></div>;
      case 'signals':   return <SignalsView />;
      case 'positions': return (
        <div className="animate-in" style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>
          <div className="card">
            <div className="card-title">💼 Open Positions</div>
            <PositionsPanel />
          </div>
          <div className="card">
            <div className="card-title">📜 Trade History</div>
            <PositionsPanel showHistory />
          </div>
        </div>
      );
      case 'news':     return <NewsCard />;
      case 'logs':     return <LogsView />;
      case 'settings': return <SettingsPanel />;
      default:         return <Dashboard />;
    }
  };

  return (
    <div className="app-layout">
      <Sidebar />
      <Topbar />
      <main className="main-content">{renderContent()}</main>
    </div>
  );
}
