'use client';
import { useStore, Position } from '@/lib/store';
import { api } from '@/lib/api';
import { useState } from 'react';

function PnlBadge({ pnl }: { pnl: number }) {
  const positive = pnl >= 0;
  return (
    <span className={`badge ${positive ? 'badge-green' : 'badge-red'}`} style={{ fontFamily: 'JetBrains Mono, monospace' }}>
      {positive ? '+' : ''}${pnl.toFixed(2)}
    </span>
  );
}

function PositionCard({ pos }: { pos: Position }) {
  const [closing, setClosing] = useState(false);
  const isOpen = pos.status === 'open';
  const pnlColor = pos.pnl_usdt >= 0 ? 'var(--green)' : 'var(--red)';

  const handleClose = async () => {
    if (!confirm('Close this position manually?')) return;
    setClosing(true);
    try { await api.closePosition(pos.id); } finally { setClosing(false); }
  };

  return (
    <div style={{
      background: 'var(--bg-base)', border: '1px solid var(--border)',
      borderRadius: 'var(--radius-md)', padding: 14,
      borderLeft: `3px solid ${pos.direction === 'BUY' ? 'var(--green)' : 'var(--red)'}`,
      marginBottom: 10, transition: 'border-color 0.2s',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontWeight: 700, fontSize: 14 }}>{pos.symbol}</span>
          <span className={`badge ${pos.direction === 'BUY' ? 'badge-green' : 'badge-red'}`}>
            {pos.direction === 'BUY' ? '▲ LONG' : '▼ SHORT'}
          </span>
          {isOpen ? (
            <span className="badge badge-blue">OPEN</span>
          ) : (
            <span className={`badge ${pos.status === 'closed_tp' ? 'badge-green' : pos.status === 'closed_sl' ? 'badge-red' : 'badge-gray'}`}>
              {pos.status === 'closed_tp' ? 'TP HIT' : pos.status === 'closed_sl' ? 'SL HIT' : 'CLOSED'}
            </span>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          {!isOpen && <PnlBadge pnl={pos.pnl_usdt} />}
          {isOpen && (
            <button className="btn btn-red btn-sm" onClick={handleClose} disabled={closing}>
              {closing ? '...' : '✕ Close'}
            </button>
          )}
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 8, fontSize: 12 }}>
        {[
          { label: 'Entry', value: `$${pos.entry_price.toLocaleString()}` },
          { label: 'Stop Loss', value: `$${pos.stop_loss_price.toLocaleString()}`, color: 'var(--red)' },
          { label: 'Take Profit', value: `$${pos.take_profit_price.toLocaleString()}`, color: 'var(--green)' },
          { label: 'Amount', value: `$${pos.amount_usdt.toFixed(2)}` },
          { label: 'Confidence', value: `${pos.confidence}%`, color: 'var(--primary)' },
          { label: 'Opened', value: new Date(pos.opened_at).toLocaleTimeString() },
        ].map((item) => (
          <div key={item.label}>
            <div style={{ color: 'var(--text-muted)', marginBottom: 2 }}>{item.label}</div>
            <div style={{ fontWeight: 600, color: item.color || 'var(--text-primary)', fontFamily: 'JetBrains Mono, monospace', fontSize: 12 }}>{item.value}</div>
          </div>
        ))}
      </div>

      {!isOpen && pos.pnl_pct !== 0 && (
        <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>P&L</span>
          <span style={{ fontWeight: 700, color: pnlColor, fontFamily: 'JetBrains Mono, monospace', fontSize: 14 }}>
            {pos.pnl_pct >= 0 ? '+' : ''}{pos.pnl_pct.toFixed(2)}%
          </span>
        </div>
      )}
    </div>
  );
}

export default function PositionsPanel({ showHistory = false }: { showHistory?: boolean }) {
  const { positions, botState } = useStore();
  const open = positions.filter(p => p.status === 'open');
  const history = botState.stats?.trade_history || [];
  const items = showHistory ? history : open;

  return (
    <div className="animate-in">
      {items.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '32px 0', color: 'var(--text-muted)', fontSize: 13 }}>
          {showHistory ? '📭 No trade history yet' : '📭 No open positions'}
        </div>
      ) : (
        items.map((pos) => <PositionCard key={(pos as Position).id} pos={pos as Position} />)
      )}
    </div>
  );
}
